"""Fetch pinned official data without starting a task or model."""

import hashlib
import importlib
import json
import tempfile
import urllib.request
from pathlib import Path

from agentbenchkit.benchmarks.featurebench import REVISION

PARQUET_SHA256 = "d775855a031b0fb5932ff7fdf4512ce733fbc6716528395bf15cbad22df5d2c3"


def fetch(destination: Path) -> None:
    if destination.exists():
        raise ValueError("destination already exists; refusing to replace dataset evidence")
    parquet = importlib.import_module("pyarrow.parquet")
    url = (
        "https://huggingface.co/datasets/LiberCoders/FeatureBench/resolve/"
        + REVISION
        + "/data/fast-00000-of-00001.parquet"
    )
    with tempfile.TemporaryDirectory(prefix="abk-fb-data-") as temporary:
        path = Path(temporary) / "fast.parquet"
        urllib.request.urlretrieve(url, path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != PARQUET_SHA256:
            raise ValueError("official parquet hash mismatch")
        rows = parquet.read_table(path).to_pylist()
        if len(rows) != 100:
            raise ValueError("expected exactly 100 Fast tasks")
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(rows, stream, ensure_ascii=False, indent=2)
