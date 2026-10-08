"""Build upstream's six-language benchmark image with the unchanged external Nexus."""

import argparse
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from agentbenchkit.benchmarks.images import NEXUS_ARCHIVE_SHA256
from agentbenchkit.benchmarks.polyglot import EVALUATOR, checked_checkout


def build(source: Path, tag: str, uv_binary: Path, nexus_archive: Path) -> None:
    checked_checkout(source, EVALUATOR)
    if uv_binary.read_bytes()[:4] != b"\x7fELF":
        raise ValueError("provide the Linux uv binary")
    if hashlib.sha256(nexus_archive.read_bytes()).hexdigest() != NEXUS_ARCHIVE_SHA256:
        raise ValueError("external Nexus archive fingerprint mismatch")
    with tempfile.TemporaryDirectory(prefix="abk-polyglot-") as temporary:
        context = Path(temporary)
        shutil.copy2(uv_binary, context / "uv")
        shutil.copy2(nexus_archive, context / "nexus.zip")
        dockerfile = (source / "benchmark/Dockerfile").read_text(encoding="utf-8")
        dockerfile = dockerfile.replace(
            "RUN curl -fsSL https://deb.nodesource.com/",
            "ENV npm_config_loglevel=verbose npm_config_fetch_timeout=30000 "
            "npm_config_fetch_retries=1\n"
            "RUN curl -fsSL https://deb.nodesource.com/",
        )
        dockerfile = dockerfile.replace(
            "npm install ", "npm install --global npm@10.9.9 && timeout 300 npm install ", 1
        )
        dockerfile += (
            "\nCOPY --from=abk uv /usr/local/bin/uv\n"
            "COPY --from=abk nexus.zip /tmp/nexus.zip\n"
            "RUN chmod +x /usr/local/bin/uv && "
            "UV_PYTHON_INSTALL_DIR=/opt/abk-python uv python install 3.12.10 && "
            "UV_PYTHON_INSTALL_DIR=/opt/abk-python uv venv --python 3.12.10 /opt/abk && "
            "uv pip install --python /opt/abk/bin/python /tmp/nexus.zip && rm /tmp/nexus.zip\n"
            # Upstream installs Rust under root. ABK runs the Agent as the host UID.
            # Only this disposable image's toolchain/cache directories are changed.
            "RUN chmod o+rx /root && chmod -R a+rX /root/.rustup && "
            "chmod -R a+rwX /root/.cargo\n"
            'ENV RUSTUP_HOME="/root/.rustup" CARGO_HOME="/root/.cargo"\n'
            'ENV PATH="/usr/local/bin:/usr/bin:/bin:/opt/abk/bin:${PATH}"\n'
            f'LABEL agentbenchkit.aider.commit="{EVALUATOR}"\n'
            "RUN nexus --version\n"
        )
        path = context / "Dockerfile"
        path.write_text(dockerfile, encoding="utf-8")
        subprocess.run(
            [
                "docker",
                "build",
                "--build-context",
                "abk=" + str(context),
                "--file",
                str(path),
                "--tag",
                tag,
                str(source.resolve()),
            ],
            check=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--uv-binary", required=True, type=Path)
    parser.add_argument("--nexus-archive", required=True, type=Path)
    args = parser.parse_args()
    build(args.source, args.tag, args.uv_binary, args.nexus_archive)
