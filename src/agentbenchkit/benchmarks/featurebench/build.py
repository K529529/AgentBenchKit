"""Build an inference-only derivative; official evaluation uses the untouched image."""

import argparse
import json
from pathlib import Path

from agentbenchkit.benchmarks.featurebench import CATALOG
from agentbenchkit.benchmarks.images import build as build_nexus_image


def build(
    image: str,
    tag: str,
    uv_binary: Path,
    nexus_archive: Path,
    source_commit: str | None = None,
    archive_sha256: str | None = None,
) -> None:
    allowed = {row["image_pin"] for row in json.loads(CATALOG.read_text(encoding="utf-8"))}
    if image not in allowed:
        raise ValueError("image must be a pinned Fast v1.1 image")
    build_nexus_image(image, tag, uv_binary, nexus_archive, source_commit, archive_sha256)


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
