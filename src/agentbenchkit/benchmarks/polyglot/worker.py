"""Execute unchanged upstream test functions without importing its model clients."""

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def official_functions(source: Path) -> dict[str, Any]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    names = {"run_unit_tests", "cleanup_test_output"}
    functions = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    if {node.name for node in functions} != names:
        raise ValueError("pinned official test entrypoints missing")
    # Compile the original AST nodes, with no changes to commands, timeout,
    # test restoration, Java annotations, log cleanup or return values.
    namespace: dict[str, Any] = {
        "Path": Path,
        "os": os,
        "re": re,
        "shutil": shutil,
        "subprocess": subprocess,
        "dump": print,
    }
    exec(compile(ast.Module(body=[*functions], type_ignores=[]), str(source), "exec"), namespace)
    return namespace


def main() -> None:
    spec = json.loads(Path("/protected/input.json").read_text())
    source = Path("/protected/benchmark.py")
    if hashlib.sha256(source.read_bytes()).hexdigest() != spec["benchmark_sha256"]:
        raise ValueError("official benchmark source fingerprint mismatch")
    for name, expected in spec["scripts_sha256"].items():
        if hashlib.sha256((Path("/aider/benchmark") / name).read_bytes()).hexdigest() != expected:
            raise ValueError("official test script fingerprint mismatch")
    Path(os.environ["HOME"]).mkdir(parents=True, exist_ok=True)
    namespace = official_functions(source)
    timed_out = False
    try:
        errors = namespace["run_unit_tests"](
            Path("/protected/original"),
            Path("/workspace") / spec["path"],
            Path("/output/test-history.md"),
            spec["test_files"],
        )
    except subprocess.TimeoutExpired:
        # This is the exact timeout outcome used by upstream run_test_real.
        timed_out = True
        errors = "Tests timed out!"
    report = {
        "passed": not bool(errors),
        "test_timeout": timed_out,
        "protocol": "single-agent-run-hidden-tests",
        "official_two_round_comparable": False,
        "entrypoint": "benchmark.benchmark.run_unit_tests",
        "benchmark_sha256": spec["benchmark_sha256"],
    }
    Path("/output/report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
