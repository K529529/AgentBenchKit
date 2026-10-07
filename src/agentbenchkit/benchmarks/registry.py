"""Benchmark selection/configuration; discovery never launches evaluated Agents."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field

from agentbenchkit.benchmarks.featurebench import EVALUATOR, REVISION, FeatureBenchAdapter
from agentbenchkit.benchmarks.micro_swe import MicroSweAdapter
from agentbenchkit.benchmarks.swebench import SweBenchAdapter
from agentbenchkit.core.models import Contract
from agentbenchkit.core.protocols import BenchmarkAdapter

NAMES = ("micro_swe", "featurebench", "swe-bench-lite")
FROZEN_EVALSET_DIGEST = "aea8cb8e68a77524805a53cd15aa471e9cec2135666c4303a63998fab4294d8d"


class BenchmarkConfig(Contract):
    schema_version: Literal[1] = 1
    benchmark: str
    task_ids: tuple[str, ...] = Field(min_length=1)
    dataset: Path | None = None
    official_source: Path | None = None
    evaluator_python: str = sys.executable
    agent_image: str | None = None
    image_pins: dict[str, str] = Field(default_factory=dict)
    agent_images: dict[str, str] = Field(default_factory=dict)
    evalset_sha256: str | None = None


def adapter(name: str, config: BenchmarkConfig | None = None) -> BenchmarkAdapter:
    if name == "micro_swe":
        return MicroSweAdapter()
    if name in {"featurebench", "swe-bench-lite"}:
        factory = FeatureBenchAdapter if name == "featurebench" else SweBenchAdapter
        return factory(
            dataset=config.dataset if config else None,
            source=config.official_source if config else None,
            evaluator_python=config.evaluator_python if config else sys.executable,
            agent_image=config.agent_image if config else None,
            image_pins=config.image_pins if config else None,
            agent_images=config.agent_images if config else None,
        )
    raise ValueError("unknown benchmark")


def make_config(
    name: str, selected: tuple[str, ...], all_tasks: bool = False, evalset: Path | None = None
) -> BenchmarkConfig:
    if sum((bool(selected), all_tasks, evalset is not None)) != 1:
        raise ValueError("choose exactly one of --task, --all-tasks, or --evalset")
    pins: dict[str, str] = {}
    digest = None
    if evalset:
        raw = evalset.read_bytes()
        data = json.loads(raw)
        canonical = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode())
        if canonical.hexdigest() != FROZEN_EVALSET_DIGEST:
            raise ValueError(
                "frozen evalset content changed; require a new explicitly approved version"
            )
        if (
            name != "featurebench"
            or data.get("evalset_id") != "featurebench-fast-evalset-v1"
            or data["source"]["revision"] != REVISION
            or data["source"]["official_evaluator_commit"] != EVALUATOR
        ):
            raise ValueError("unsupported evalset or revision")
        selected = tuple(data["task_ids"])
        pins = {row["image"]: row["pull_reference"] for row in data["images"]}
        digest = hashlib.sha256(raw).hexdigest()
    tasks = adapter(name).load_tasks(selected)
    return BenchmarkConfig(
        benchmark=name,
        task_ids=tuple(t.task_id for t in tasks),
        image_pins=pins,
        evalset_sha256=digest,
    )
