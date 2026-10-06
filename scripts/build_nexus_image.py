"""Build from an existing unmodified Nexus checkout; no credentials in the context."""

import argparse
import subprocess
from pathlib import Path

PIN = "677fc997dcdc2f369fa8d4a667d400de99e35f84"
parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path, help="existing Nexus Git repository containing v0.2.0")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
context = root / ".agentbenchkit" / "docker-build"
context.mkdir(parents=True, exist_ok=True)
subprocess.run(
    [
        "git",
        "-C",
        str(args.source.resolve()),
        "archive",
        "--format=zip",
        "-o",
        str(context / "nexus-v0.2.0.zip"),
        PIN,
    ],
    check=True,
)
(context / "Dockerfile").write_bytes((root / "docker" / "Dockerfile.nexus").read_bytes())
subprocess.run(["docker", "build", "-t", "agentbenchkit-nexus:v0.2.0", str(context)], check=True)
