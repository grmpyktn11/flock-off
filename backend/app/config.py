"""Where the service gets its data.

DATABASE_URL unset means use app.mock_data. That keeps the test suite and
a fresh checkout working with no infrastructure, and makes talking to a
real database a deliberate choice rather than an accident.
"""

import os
from pathlib import Path

# The repo root .env, so the backend and the ingestion job read one file.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _load_env_file() -> None:
    """Minimal .env reader: KEY=value lines, # comments, no interpolation.

    A dependency for this would be three lines of behaviour behind a
    package. Real deployments set environment variables directly and never
    reach this path.
    """
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_MOCK_CAMERAS = DATABASE_URL == ""

# Same rule: unset means use the mock router.
VALHALLA_URL = os.environ.get("VALHALLA_URL", "").rstrip("/")
USE_MOCK_ROUTING = VALHALLA_URL == ""

# A cold Valhalla call on a large exclusion set is slower than a warm one,
# but nothing here should take seconds.
VALHALLA_TIMEOUT_S = 20

# Cameras further than this from the trip's bounding box are not worth
# fetching. Wide enough to cover a real detour.
BBOX_PADDING_M = 3000.0
