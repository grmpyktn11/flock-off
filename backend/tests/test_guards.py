"""The two things standing between a public URL and a Google bill."""

import pytest
from fastapi.testclient import TestClient

from app import config, ratelimit
from app.main import app
from app.ratelimit import limiter

client = TestClient(app)

TRIP = {
    "origin": {"lat": 38.9696, "lng": -77.3861},
    "destination": {"lat": 38.8462, "lng": -77.3064},
}


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


def test_the_allowance_runs_out():
    """/search allows 30 a minute. The thirty-first is refused."""
    for _ in range(30):
        assert client.get("/search", params={"q": "metro"}).status_code == 200

    assert client.get("/search", params={"q": "metro"}).status_code == 429


def test_refusal_says_when_to_come_back():
    """Retry-After is what stops a client retrying immediately and making
    the problem worse."""
    for _ in range(30):
        client.get("/search", params={"q": "metro"})

    refused = client.get("/search", params={"q": "metro"})
    assert refused.status_code == 429
    assert int(refused.headers["Retry-After"]) >= 1
    # The app reads `detail` off every other error this API returns, so a
    # 429 has to speak the same shape or the driver sees a status code.
    assert refused.json()["detail"]


def test_endpoints_have_separate_allowances():
    """Exhausting search must not close planning. They cost different
    amounts, and a driver who typed a lot should still get their route."""
    for _ in range(30):
        client.get("/search", params={"q": "metro"})
    assert client.get("/search", params={"q": "metro"}).status_code == 429

    assert client.post("/plan", json=TRIP).status_code == 200


def test_plan_and_replan_share_one_allowance():
    """A re-plan is the same pipeline at the same Google cost, so it spends
    from the same allowance rather than letting an address ask for twice as
    much by alternating."""
    for _ in range(10):
        assert client.post("/plan", json=TRIP).status_code == 200

    replan = client.post(
        "/replan",
        json={"current": TRIP["origin"], "destination": TRIP["destination"]},
    )
    assert replan.status_code == 429


def test_health_is_never_limited():
    """Uptime checks poll far harder than any driver and must not be
    mistaken for abuse."""
    for _ in range(60):
        assert client.get("/health").status_code == 200


def test_the_window_moves():
    """A fixed window resets on the minute, so a scraper can send a full
    allowance at 12:00:59 and another at 12:01:01. A moving window counts
    the trailing sixty seconds and has no boundary to exploit."""
    assert limiter._strategy == "moving-window"


def test_plan_still_reads_its_body():
    """The body parameter had to be renamed off `request` to make room for
    slowapi, which is exactly the kind of rename that silently stops a
    handler seeing its input."""
    body = client.post("/plan", json=TRIP).json()
    assert "deep_link" in body
    assert body["baseline_eta_seconds"] > 0


# --------------------------------------------------------------------------
# App key
# --------------------------------------------------------------------------


def test_unset_key_leaves_the_service_open():
    """A fresh checkout runs with no configuration, matching how the rest
    of app.config treats missing settings."""
    assert config.APP_KEY == ""
    assert client.get("/search", params={"q": "metro"}).status_code == 200


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setattr(config, "APP_KEY", "s3cret")
    ratelimit.reset()


def test_billed_endpoints_refuse_a_missing_key(keyed):
    assert client.get("/search", params={"q": "metro"}).status_code == 401
    assert client.get("/place", params={"place_id": "x"}).status_code == 401
    assert client.post("/plan", json=TRIP).status_code == 401
    assert (
        client.post(
            "/replan",
            json={"current": TRIP["origin"], "destination": TRIP["destination"]},
        ).status_code
        == 401
    )


def test_a_wrong_key_is_refused(keyed):
    response = client.get(
        "/search", params={"q": "metro"}, headers={"X-App-Key": "wrong"}
    )
    assert response.status_code == 401


def test_the_right_key_passes(keyed):
    response = client.get(
        "/search", params={"q": "metro"}, headers={"X-App-Key": "s3cret"}
    )
    assert response.status_code == 200


def test_health_needs_no_key(keyed):
    """So an uptime check does not need to hold the secret."""
    assert client.get("/health").status_code == 200
