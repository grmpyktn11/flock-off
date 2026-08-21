"""Pin the test suite to the mock camera source.

A .env with DATABASE_URL in it is normal on a development machine, and
without this the suite would quietly start asserting mock expectations
against real Fairfax cameras and fail for the wrong reason. Tests that
want the real database ask for it explicitly.
"""

import pytest

from app import config


@pytest.fixture(autouse=True)
def use_mock_cameras(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCK_CAMERAS", True)
