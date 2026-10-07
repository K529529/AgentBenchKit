"""Build an inference-only derivative; official evaluation uses the untouched image."""

import argparse
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

NEXUS_ARCHIVE_SHA256 = "b7993371ff87513f32ce4705bf7b308178caf970f289b8b15e248751af778c42"


def build(image: str, tag: str, uv_binary: Path, nexus_archive: Path) -> None:
    if "@sha256:" not in image or len(image.rsplit(":", 1)[-1]) != 64:
        raise ValueError("an immutable official image digest is required")
    if uv_binary.read_bytes()[:4] != b"\x7fELF":
        raise ValueError("provide the Linux uv executable")
    if hashlib.sha256(nexus_archive.read_bytes()).hexdigest() != NEXUS_ARCHIVE_SHA256:
        raise ValueError("Nexus archive differs from the accepted V0 external Agent")
    with tempfile.TemporaryDirectory(prefix="abk-image-") as temporary:
        context = Path(temporary)
        shutil.copy2(uv_binary, context / "uv")
        shutil.copy2(nexus_archive, context / "nexus.zip")
        (context / "Dockerfile").write_text(
            f'FROM {image}\nLABEL agentbenchkit.benchmark.base="{image}"\n'
            "COPY uv /usr/local/bin/uv\nCOPY nexus.zip /tmp/nexus.zip\n"
            "RUN chmod +x /usr/local/bin/uv && "
            "UV_PYTHON_INSTALL_DIR=/opt/abk-python uv python install 3.12.10 && "
            "UV_PYTHON_INSTALL_DIR=/opt/abk-python uv venv --python 3.12.10 /opt/abk && "
            "uv pip install --python /opt/abk/bin/python /tmp/nexus.zip && rm /tmp/nexus.zip\n"
            'ENV PATH="/opt/miniconda3/envs/testbed/bin:/opt/abk/bin:${PATH}"\n'
            "RUN nexus --version\n",
            encoding="utf-8",
        )
        subprocess.run(["docker", "build", "--tag", tag, str(context)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--uv-binary", type=Path, required=True)
    parser.add_argument("--nexus-archive", type=Path, required=True)
    args = parser.parse_args()
    build(args.image, args.tag, args.uv_binary, args.nexus_archive)
