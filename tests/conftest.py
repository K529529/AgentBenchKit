"""Keep pytest temporary files in the ignored project runtime directory."""

import os
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    if not config.option.basetemp and "PYTEST_DEBUG_TEMPROOT" not in os.environ:
        root = Path(__file__).resolve().parents[1] / ".agentbenchkit" / "pytest"
        root.mkdir(parents=True, exist_ok=True)
        os.environ["PYTEST_DEBUG_TEMPROOT"] = str(root)
