import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_runtime import ControlledHarness

from agentbenchkit.benchmarks.micro_swe import load_tasks
from agentbenchkit.runtime.runner import evaluate
from agentbenchkit.viewer.app import artifact_path, create_app


async def test_viewer_routes_are_readonly_and_escape_html(tmp_path: Path) -> None:
    task = load_tasks(("clamp",))[0].model_copy(update={"prompt": "<script>alert(1)</script>"})
    directory = await evaluate([task], ControlledHarness(True), tmp_path)
    sample = next(directory.glob("tasks/*/*/sample.json"))
    before = {
        p.relative_to(directory).as_posix(): p.read_bytes()
        for p in directory.rglob("*")
        if p.is_file()
    }
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/").status_code == 200
        assert client.get(f"/runs/{directory.name}").status_code == 200
        response = client.get(f"/runs/{directory.name}/samples/{sample.parent.name}")
        assert response.status_code == 200
        assert "repeated-tool-calls-v1" in response.text
        assert "UNAVAILABLE" in response.text
        assert "&lt;script&gt;" in response.text
        assert "<script>alert(1)</script>" not in response.text
        assert response.headers["x-content-type-options"] == "nosniff"
        assert (
            client.get(
                "/compare", params={"baseline": directory.name, "candidate": directory.name}
            ).status_code
            == 200
        )
        for path in ["../auth.json", "work/secret.json", "owner.lock", "/etc/passwd"]:
            assert (
                client.get(f"/runs/{directory.name}/artifact", params={"path": path}).status_code
                == 404
            )
        assert client.post("/").status_code == 405
        assert client.get("/", headers={"host": "attacker.invalid"}).status_code == 400
    after = {
        p.relative_to(directory).as_posix(): p.read_bytes()
        for p in directory.rglob("*")
        if p.is_file()
    }
    assert before == after
    assert json.loads(sample.read_bytes())["sample_success"] is True


def test_artifact_response_size_limit(tmp_path: Path) -> None:
    candidate = tmp_path / "tasks/t/s/candidate/large.py"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"x" * 1_000_001)
    with pytest.raises(ValueError, match="limit"):
        artifact_path(tmp_path, "tasks/t/s/candidate/large.py")
