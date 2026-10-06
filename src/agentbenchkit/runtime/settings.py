"""Build an isolated Agent home; never serialize credential values."""

import json
import os
import tomllib
from pathlib import Path
from typing import Any

from agentbenchkit.storage.artifacts import Redactor


class NexusSettings:
    def __init__(self, source: Path, max_steps: int | None = None) -> None:
        with source.open("rb") as stream:
            config = tomllib.load(stream)
        self.model: dict[str, Any] = config["model"]
        self.max_steps = max_steps or int(config.get("runtime", {}).get("max_steps", 40))
        self.key_name = str(self.model.get("api_key_env", "NEXUS_MODEL_API_KEY"))
        self.secret = os.environ.get(self.key_name, "")
        if not self.secret:
            raise ValueError(f"missing credential environment variable: {self.key_name}")
        self.redactor = Redactor((self.secret,))
        if any(key in self.model for key in ("api_key", "token", "authorization")):
            raise ValueError(
                "model configuration must reference an environment variable, not a key"
            )

    def prepare(self, home: Path) -> dict[str, str]:
        config_dir = home / ".nexus"
        config_dir.mkdir(parents=True, exist_ok=True)
        lines = ["[model]"]
        for key, value in self.model.items():
            if not key.replace("_", "").isalnum():
                raise ValueError("invalid model setting name")
            if not isinstance(value, (str, bool, int, float)):
                raise ValueError("unsupported model setting value")
            lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
        lines.extend(["", "[runtime]", f"max_steps = {self.max_steps}"])
        text = "\n".join(lines) + "\n"
        if self.secret in text:
            raise ValueError("credential value cannot be persisted in Agent configuration")
        (config_dir / "config.toml").write_text(text, encoding="utf-8")
        return {"HOME": str(home), "USERPROFILE": str(home), self.key_name: self.secret}

    def manifest(self) -> dict[str, Any]:
        return {
            "model": self.redactor.value(self.model),
            "max_steps": self.max_steps,
            "tools": None,
            "sampling_parameters": None,
            "mcp_servers": [],
            "skills": [],
            "credential_source": self.key_name,
        }
