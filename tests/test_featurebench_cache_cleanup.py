import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agentbenchkit.benchmarks.featurebench import worker


@pytest.mark.parametrize("cache_cleanup_ok", [True, False])
def test_prepare_clears_official_caches_before_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cache_cleanup_ok: bool
) -> None:
    calls: list[str] = []
    container = SimpleNamespace(
        id="prepared-container",
        stop=lambda **kwargs: calls.append("stop"),
        remove=lambda **kwargs: calls.append("remove"),
    )
    instance = SimpleNamespace(get_docker_runtime_config=lambda: {})
    manager = SimpleNamespace(
        client=SimpleNamespace(
            images=SimpleNamespace(
                get=lambda image: SimpleNamespace(labels={"agentbenchkit.benchmark.base": "pinned"})
            )
        ),
        create_container=lambda *args, **kwargs: container,
    )

    def initialize(*args: Any) -> bool:
        calls.append("initialize")
        return True

    def clear_caches(*args: Any) -> bool:
        calls.append("clear_caches")
        return cache_cleanup_ok

    handler = SimpleNamespace(initialize_runtime=initialize, clear_package_caches=clear_caches)
    modules = {
        "featurebench.infer.container": SimpleNamespace(ContainerManager=lambda logger: manager),
        "featurebench.infer.models": SimpleNamespace(
            TaskInstance=SimpleNamespace(from_dict=lambda row: instance)
        ),
        "featurebench.infer.runtime": SimpleNamespace(RuntimeHandler=lambda cm: handler),
    }
    monkeypatch.setattr(importlib, "import_module", lambda name: modules[name])
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda args, **kwargs: "fixed" if "rev-parse" in args else "",
    )
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: calls.append(args[1]))
    monkeypatch.setattr(shutil, "copytree", lambda *args, **kwargs: calls.append("baseline"))
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec = {
        "source": str(tmp_path),
        "commit": "fixed",
        "mode": "prepare",
        "row": {"image_name": "pinned"},
        "agent_image": "inference",
        "workspace": str(tmp_path / "workspace"),
        "container": "container",
        "snapshot": "snapshot",
    }
    if cache_cleanup_ok:
        worker.main(spec, tmp_path)
        assert calls == ["initialize", "clear_caches", "stop", "cp", "baseline", "commit", "remove"]
    else:
        with pytest.raises(RuntimeError, match="package-cache cleanup failed"):
            worker.main(spec, tmp_path)
        assert calls == ["initialize", "clear_caches", "remove"]

    records = [json.loads(line) for line in (tmp_path / "timings.jsonl").read_text().splitlines()]
    cleanup_record = next(row for row in records if row["stage"] == "package_cache_cleanup")
    assert cleanup_record["status"] == ("ok" if cache_cleanup_ok else "error")
    assert all(row["duration_ms"] >= 0 for row in records)
    assert any(row["stage"] == "snapshot_commit" for row in records) is cache_cleanup_ok
