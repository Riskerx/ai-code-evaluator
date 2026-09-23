from pathlib import Path

import pytest


@pytest.fixture
def examples():
    return Path(__file__).resolve().parents[1] / "examples"

