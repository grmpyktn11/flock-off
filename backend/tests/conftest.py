"""Pin the test suite to the mock camera source.

A .env with real credentials in it is normal on a development machine,
and without this the suite would quietly assert mock expectations against
real services and fail for the wrong reason. Tests that want the real
ones ask for them explicitly.

Google matters most here: those calls are billed, so a test suite that
reaches them costs money every run and fails in CI where no key exists.
"""

import pytest

from app import config


@pytest.fixture(autouse=True)
def use_mock_sources(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCK_CAMERAS", True)
    monkeypatch.setattr(config, "USE_MOCK_ROUTING", True)
    monkeypatch.setattr(config, "USE_MOCK_GOOGLE", True)
