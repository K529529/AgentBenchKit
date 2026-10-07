"""Isolated Linux worker. All test execution and grading remain upstream-owned."""

import hashlib
import importlib
import json
import logging
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
    row = spec["row"]
    if spec["mode"] == "verify":
        module = importlib.import_module("featurebench.harness.run_evaluation")
        pandas = importlib.import_module("pandas")

        class RegisteredCleanup(module.EvalContainerCleanup):  # type: ignore[name-defined,misc]
            def container_labels(
                self, instance_id: str, n_attempt: int, purpose: str = "eval"
            ) -> dict[str, str]:
                labels: dict[str, str] = super().container_labels(instance_id, n_attempt, purpose)
                labels.update(
                    {
                        "agentbenchkit.managed": "true",
                        "agentbenchkit.execution": spec["run_label"],
                        "agentbenchkit.workspace": hashlib.sha256(
                            spec["resource_workspace"].encode()
                        ).hexdigest(),
                    }
                )
                return labels

        cleanup = RegisteredCleanup(spec["run_label"], module.console)
        result = module.run_instance(
            pandas.Series(row),
            {"instance_id": row["instance_id"], "model_patch": spec["patch"], "n_attempt": 1},
            directory,
            timeout=spec["timeout"],
            white=False,
            container_cleanup=cleanup,
        )
        (directory / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return
    containers = importlib.import_module("featurebench.infer.container")
    models = importlib.import_module("featurebench.infer.models")
    runtime = importlib.import_module("featurebench.infer.runtime")
    manager = containers.ContainerManager(logging.getLogger("abk.featurebench"))
    image = manager.client.images.get(spec["agent_image"])
    if image.labels.get("agentbenchkit.benchmark.base") != row["image_name"]:
        raise ValueError("Agent image does not declare this task's pinned official base image")
    instance = models.TaskInstance.from_dict(row)
    workspace = Path(spec["workspace"])
    labels = {
        "agentbenchkit.managed": "true",
        "agentbenchkit.workspace": hashlib.sha256(str(workspace).encode()).hexdigest(),
    }
    container = manager.create_container(
        spec["agent_image"],
        container_name=spec["container"],
        labels=labels,
        docker_runtime_config=instance.get_docker_runtime_config(),
    )
    try:
        handler = runtime.RuntimeHandler(manager)
        if not handler.initialize_runtime(container, instance, directory / "official-prepare.log"):
            raise RuntimeError("official FeatureBench initialization failed")
        # The original unmasked source and stale bytecode are removed by upstream.
        container.stop(timeout=10)
        workspace.mkdir(parents=True)
        subprocess.run(["docker", "cp", f"{container.id}:/testbed/.", str(workspace)], check=True)
        shutil.copytree(
            workspace,
            workspace.parent / "baseline",
            symlinks=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__"),
        )
        # Snapshotting a large official image can exceed docker-py's 60 s default.
        # This is ABK environment materialization, not an evaluator semantic change.
        subprocess.run(
            ["docker", "commit", container.id, spec["snapshot"]],
            check=True,
            timeout=600,
        )
    finally:
        container.remove(force=True)


if __name__ == "__main__":
    path = Path(sys.argv[1])
    main(json.loads(path.read_text(encoding="utf-8")), path.parent)
