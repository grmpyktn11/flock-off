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

# Same rule again: no key means use the mock Google.
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
USE_MOCK_GOOGLE = GOOGLE_API_KEY == ""
GOOGLE_TIMEOUT_S = 10

# Same rule again: no key means use the canned explainer. The real one
# asks Claude why a camera is plausibly where it is, once per camera -
# the answer is cached in the cameras row after that.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
USE_MOCK_EXPLAIN = ANTHROPIC_API_KEY == ""
# Sonnet, not Haiku: the note argues a conclusion from given facts, and
# Haiku kept inventing receipts ("12 injury crashes (VDOT)") under that
# brief. Each note is generated once ever, so the cost stays trivial.
EXPLAIN_MODEL = "claude-sonnet-5"
EXPLAIN_TIMEOUT_S = 30
# How many batches that generate NEW explanations each install may put on
# the server's key before the app asks for the user's own. Serving cached
# explanations never counts - those cost nothing.
FREE_EXPLAIN_BATCHES = 3

# A shared secret the app sends as X-App-Key. Not authentication - it
# ships inside every APK and anyone can read it out - but it costs a
# scanner one more step than finding an open endpoint, and most of them
# do not take it. Unset means open, so a fresh checkout still runs.
APP_KEY = os.environ.get("APP_KEY", "")

# Cameras further than this from the trip's bounding box are not worth
# fetching. Wide enough to cover a real detour.
BBOX_PADDING_M = 3000.0
