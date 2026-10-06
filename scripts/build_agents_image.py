"""Add pinned official Codex to the Nexus image without credentials in the build."""

import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
context = root / ".agentbenchkit" / "codex-build"
context.mkdir(parents=True, exist_ok=True)
asset = "codex-package-x86_64-unknown-linux-musl.tar.gz"
if not (context / asset).exists():
    subprocess.run(
        [
            "gh",
            "release",
            "download",
            "rust-v0.155.1",
            "--repo",
            "openai/codex",
            "--pattern",
            asset,
            "--dir",
            str(context),
        ],
        check=True,
    )
(context / ".dockerignore").write_text(f"*\n!Dockerfile\n!{asset}\n", encoding="utf-8")
(context / "Dockerfile").write_bytes((root / "docker/Dockerfile.agents").read_bytes())
subprocess.run(["docker", "build", "-t", "agentbenchkit-agents:v0", str(context)], check=True)
