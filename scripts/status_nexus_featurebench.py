"""Read-only status for a detached frozen FeatureBench batch."""

import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
args = parser.parse_args()
output = args.output
for name in ("process.json", "exit.json", "stop-reason.json"):
    path = output / name
    if path.exists():
        data = json.loads(path.read_text())
        if name == "process.json":
            try:
                os.kill(data["pid"], 0)
                data["pid_alive"] = True
            except ProcessLookupError:
                data["pid_alive"] = False
        print(name, json.dumps(data))
for directory in sorted((output / "runs").glob("*")):
    if not directory.is_dir():
        continue
    print("run", directory.name)
    summary = directory / "summary.json"
    if summary.exists():
        print(summary.read_text())
    for path in sorted(directory.glob("tasks/*/*/executions/*/execution.json")):
        data = json.loads(path.read_text())
        log = path.parent / "stdout.log"
        print(
            data["task_id"],
            data.get("phase"),
            data.get("execution_status"),
            "agent_started=",
            data.get("agent_started"),
            "stdout_bytes=",
            log.stat().st_size if log.exists() else 0,
        )
