"""Build an inference-only derivative; official evaluation uses the untouched image."""

import argparse
import hashlib
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

NEXUS_ARCHIVE_SHA256 = "b7993371ff87513f32ce4705bf7b308178caf970f289b8b15e248751af778c42"


def build(
    image: str,
    tag: str,
    uv_binary: Path,
    nexus_archive: Path,
    source_commit: str | None = None,
    archive_sha256: str | None = None,
) -> None:
    if "@sha256:" not in image or len(image.rsplit(":", 1)[-1]) != 64:
        raise ValueError("an immutable official image digest is required")
    if uv_binary.read_bytes()[:4] != b"\x7fELF":
        raise ValueError("provide the Linux uv executable")
    expected = archive_sha256 or NEXUS_ARCHIVE_SHA256
    if hashlib.sha256(nexus_archive.read_bytes()).hexdigest() != expected:
        raise ValueError("Nexus archive SHA256 mismatch")
    if source_commit is not None:
        if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or archive_sha256 is None:
            raise ValueError("explicit source requires full commit and archive SHA256")
        with zipfile.ZipFile(nexus_archive) as archive:
            if archive.comment.decode("ascii") != source_commit:
                raise ValueError("git archive commit does not match requested source")
    elif archive_sha256 is not None:
        raise ValueError("explicit archive SHA256 requires source commit")
    commit = source_commit or "677fc997dcdc2f369fa8d4a667d400de99e35f84"
    with tempfile.TemporaryDirectory(prefix="abk-image-") as temporary:
        context = Path(temporary)
        shutil.copy2(uv_binary, context / "uv")
        shutil.copy2(nexus_archive, context / "nexus.zip")
        (context / "Dockerfile").write_text(
            f'FROM {image}\nLABEL agentbenchkit.benchmark.base="{image}"\n'
            f'LABEL agentbenchkit.nexus.commit="{commit}"\n'
            f'LABEL agentbenchkit.nexus.archive-sha256="{expected}"\n'
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
    parser.add_argument("--source-commit")
    parser.add_argument("--archive-sha256")
    args = parser.parse_args()
    build(
        args.image,
        args.tag,
        args.uv_binary,
        args.nexus_archive,
        args.source_commit,
        args.archive_sha256,
    )
