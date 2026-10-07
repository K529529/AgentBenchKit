"""Invoke the pinned SWE-bench evaluator; only resource ownership is ABK-owned."""

import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def main(spec: dict[str, Any], directory: Path) -> None:
    source = Path(spec["source"])
    commit = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True)
    if commit != spec["commit"] or dirty:
        raise ValueError("official evaluator checkout must be clean and exactly pinned")
    sys.path.insert(0, str(source))
    docker = importlib.import_module("docker")
    client = docker.from_env(timeout=1800)
    identity = hashlib.sha256(
        spec.get("workspace", spec["resource_workspace"]).encode()
    ).hexdigest()
    labels = {
        "agentbenchkit.managed": "true",
        "agentbenchkit.workspace": identity,
        "agentbenchkit.execution": spec.get("run_label", "prepare"),
    }
    if spec["mode"] == "prepare":
        container = client.containers.create(
            spec["agent_image"],
            name=spec["container"],
            command="tail -f /dev/null",
            labels=labels,
            detach=True,
        )
        try:
            container.start()
            for args in (["reset", "--hard", spec["row"]["base_commit"]], ["clean", "-fd"]):
                result = container.exec_run(
                    ["git", "-c", "safe.directory=/testbed", *args], workdir="/testbed"
                )
                print(result.output.decode("utf-8", "replace"), flush=True)
                if result.exit_code:
                    raise RuntimeError("official image baseline preparation failed")
            container.stop(timeout=10)
            workspace = Path(spec["workspace"])
            workspace.mkdir(parents=True)
            subprocess.run(
                ["docker", "cp", f"{container.id}:/testbed/.", str(workspace)],
                check=True,
                timeout=300,
            )
            shutil.copytree(
                workspace,
                workspace.parent / "baseline",
                symlinks=True,
                ignore=shutil.ignore_patterns(".git", "__pycache__"),
            )
        finally:
            container.remove(force=True)
        return
    module: Any = importlib.import_module("swebench.harness.run_evaluation")
    specs = importlib.import_module("swebench.harness.test_spec.test_spec")
    original = specs.make_test_spec(spec["row"], namespace="swebench", arch="x86_64")

    class PinnedSpec(specs.TestSpec):  # type: ignore[name-defined,misc]
        @property
        def instance_image_key(self) -> str:
            return str(spec["official_image"])

    class TrackedContainers:
        def __getattr__(self, name: str) -> Any:
            return getattr(client.containers, name)

        def create(self, *args: Any, **kwargs: Any) -> Any:
            kwargs["labels"] = {**kwargs.get("labels", {}), **labels}
            return client.containers.create(*args, **kwargs)

    class TrackedClient:
        containers = TrackedContainers()

        def __getattr__(self, name: str) -> Any:
            return getattr(client, name)

    test_spec = PinnedSpec(**vars(original))
    module.RUN_EVALUATION_LOG_DIR = directory / "official"
    prediction = {
        "instance_id": spec["row"]["instance_id"],
        "model_name_or_path": "agent",
        "model_patch": spec["patch"],
    }
    result = module.run_instance(
        test_spec,
        prediction,
        False,
        False,
        TrackedClient(),
        spec["run_label"],
        timeout=spec["timeout"],
    )
    report = (
        directory
        / "official"
        / spec["run_label"]
        / "agent"
        / spec["row"]["instance_id"]
        / "report.json"
    )
    result["report"] = json.loads(report.read_text()) if report.exists() else {}
    (directory / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    path = Path(sys.argv[1]).resolve()
    main(json.loads(path.read_text(encoding="utf-8")), path.parent)
