"""Dedicated loopback viewer entry point; does not import or invoke the evaluation CLI."""

import argparse
from pathlib import Path

import uvicorn

from agentbenchkit.viewer.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only ABK analysis workbench")
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    uvicorn.run(
        create_app(args.root[0], tuple(args.root[1:])),
        host="127.0.0.1",
        port=args.port,
        limit_concurrency=8,
    )


if __name__ == "__main__":
    main()
