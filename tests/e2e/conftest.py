"""E2E test configuration."""

import pytest


@pytest.fixture
def base_url():
    return "http://localhost:8000"
