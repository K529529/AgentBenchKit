"""Fetch pinned official data without starting a task or model."""

import hashlib
import importlib
import json
import tempfile
import urllib.request
from pathlib import Path

from agentbenchkit.benchmarks.swebench import REVISION

PARQUET_SHA256 = "7a21f37b8bc179c7db5beeb14e88ac538ba283455c776e6b2535bbfb6e3551b4"


def fetch(destination: Path) -> None:
    if destination.exists():
        raise ValueError("destination already exists; refusing to replace dataset evidence")
    parquet = importlib.import_module("pyarrow.parquet")
    url = (
        "https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite/resolve/"
        + REVISION
        + "/data/test-00000-of-00001.parquet"
    )
    with tempfile.TemporaryDirectory(prefix="abk-swe-data-") as temporary:
        path = Path(temporary) / "test.parquet"
        urllib.request.urlretrieve(url, path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != PARQUET_SHA256:
            raise ValueError("official parquet hash mismatch")
        rows = parquet.read_table(path).to_pylist()
        if len(rows) != 300:
            raise ValueError("expected exactly 300 Lite tasks")
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(rows, stream, ensure_ascii=False, indent=2)
