"""Shared credential resolution and isolated configuration; no Agent-specific model schema."""

import base64
import json
import os
import tomllib
from pathlib import Path
from typing import Any

from agentbenchkit.core.models import HarnessOptions, ModelSpec
from agentbenchkit.core.protocols import Harness
from agentbenchkit.storage.artifacts import Redactor


def load_model(path: Path) -> ModelSpec:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix == ".json" else tomllib.loads(text)
    return ModelSpec.model_validate(data)


class AgentSettings:
    def __init__(
        self,
        harness: Harness,
        model: ModelSpec,
        options: HarnessOptions | None = None,
        auth_file: Path | None = None,
    ) -> None:
        self.requested_model = model
        self.native = harness.native_config(model, options or HarnessOptions())
        self.model = self.native.effective_model
        self.auth: str | None = None
        self.key = ""
        self.private_files: dict[str, str] = {}
        if model.credential.kind == "api_key":
            if auth_file is not None:
                raise ValueError("auth cache conflicts with API-key ModelSpec")
            assert model.credential.env_var is not None
            self.key = os.environ.get(model.credential.env_var, "")
            if not self.key:
                raise ValueError(
                    f"missing credential environment variable: {model.credential.env_var}"
                )
            secrets = [self.key]
        elif self.native.credential_files:
            if auth_file is None or not auth_file.is_dir():
                raise ValueError("account login requires an explicit credential directory")
            secrets = []
            for name in self.native.credential_files:
                source = auth_file / name
                if source.is_symlink() or not source.resolve().is_relative_to(auth_file.resolve()):
                    raise ValueError("credential file escapes the explicit directory")
                if source.stat().st_size > 65536:
                    raise ValueError("credential file exceeds 64 KiB")
                raw = source.read_bytes()
                encoded = base64.b64encode(raw).decode()
                self.private_files[name] = encoded
                secrets.append(encoded)
                try:
                    secrets.append(raw.decode("utf-8"))
                except UnicodeDecodeError:
                    pass
        else:
            if auth_file is None or self.native.credential_file is None:
                raise ValueError(
                    "ChatGPT smoke requires an explicit auth cache and compatible Harness"
                )
            self.auth = auth_file.read_text(encoding="utf-8")
            data = json.loads(self.auth)
            if data.get("auth_mode") != "chatgpt":
                raise ValueError("expected ChatGPT auth cache")
            secrets = [
                self.auth,
                *(str(value) for value in data.get("tokens", {}).values() if value),
            ]
        self.redactor = Redactor(tuple(secrets))
        if self.redactor.text(self.native.config_toml) != self.native.config_toml:
            raise ValueError("credential value cannot be persisted in native configuration")

    def prepare(self, home: Path) -> dict[str, str]:
        config_dir = home / self.native.config_directory
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.toml").write_text(self.native.config_toml, encoding="utf-8")
        effective_home = "/agent-private/home" if self.auth or self.private_files else str(home)
        env = {"HOME": effective_home, "USERPROFILE": effective_home}
        if self.native.config_home_env:
            env[self.native.config_home_env] = (
                effective_home + "/" + self.native.config_directory
                if self.auth or self.private_files
                else str(config_dir)
            )
        if self.auth or self.private_files:
            env["ABK_MEMORY_HOME"] = json.dumps(
                {
                    "directory": self.native.config_directory,
                    "config": self.native.config_toml,
                    "credential_file": self.native.credential_file,
                    "auth": self.auth,
                    "files": self.private_files,
                }
            )
        else:
            assert self.native.credential_env is not None
            env[self.native.credential_env] = self.key
        return env

    def manifest(self) -> dict[str, Any]:
        return {
            "native_config": self.native.config_toml,
            "wire_api": self.native.wire_api,
            "controls": self.native.controls,
            "config_home": "isolated",
            "credential_source": self.model.credential.model_dump(),
            "evaluation_class": "subscription_smoke"
            if self.auth or self.private_files
            else "explicit_api",
        }
