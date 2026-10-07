"""Build an inference-only derivative; official evaluation uses the untouched image."""

import argparse
import json
from pathlib import Path

from agentbenchkit.benchmarks.featurebench import CATALOG
from agentbenchkit.benchmarks.images import build as build_nexus_image


def build(image: str, tag: str, uv_binary: Path, nexus_archive: Path) -> None:
    allowed = {row["image_pin"] for row in json.loads(CATALOG.read_text(encoding="utf-8"))}
    if image not in allowed:
        raise ValueError("image must be a pinned Fast v1.1 image")
    build_nexus_image(image, tag, uv_binary, nexus_archive)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--uv-binary", type=Path, required=True)
    parser.add_argument("--nexus-archive", type=Path, required=True)
    args = parser.parse_args()
    build(args.image, args.tag, args.uv_binary, args.nexus_archive)
