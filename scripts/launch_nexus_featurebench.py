"""Read required credentials from stdin and start an independent tmux evaluation."""

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--plan", type=Path, required=True)
parser.add_argument("--group", choices=("single", "multi"), required=True)
args = parser.parse_args()
plan = json.loads(args.plan.read_text())
material = json.load(sys.stdin)
if set(material) != set(plan["credential_env"]) or not all(material.values()):
    raise ValueError("missing or unexpected credential environment names")
for other, directory in plan["outputs"].items():
    prior = Path(directory)
    if other != args.group and prior.exists() and not (prior / "exit.json").exists():
        raise RuntimeError("another group has no completion marker; inspect before starting")
output = Path(plan["outputs"][args.group])
output.mkdir(parents=True, exist_ok=False)
fd, name = tempfile.mkstemp(prefix="abk-credential-", dir="/tmp")
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(material, stream)
    repository = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        str(repository / "scripts/run_nexus_featurebench.py"),
        "--plan",
        str(args.plan.resolve()),
        "--group",
        args.group,
        "--output",
        str(output),
        "--credential-file",
        name,
    ]
    shell = (
        "exec "
        + shlex.join(command)
        + " > "
        + shlex.quote(str(output / "stdout-stderr.log"))
        + " 2>&1"
    )
    session = plan["sessions"][args.group]
    subprocess.run(
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            session,
            "-c",
            str(repository),
            "env",
            "PYTHONPATH=" + str(repository / "src"),
            "bash",
            "-lc",
            shell,
        ],
        check=True,
    )
    print(
        json.dumps(
            {"session": session, "output": str(output), "state": "LAUNCHED_NOT_YET_VERIFIED"}
        )
    )
except BaseException:
    Path(name).unlink(missing_ok=True)
    raise
