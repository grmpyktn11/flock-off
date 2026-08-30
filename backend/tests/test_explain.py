"""POST /explanations: the "why would a camera be here" feature.

The mock path is exercised through the endpoint; the real path's caching
and failure handling are unit-tested with the Claude call stubbed out, so
nothing here spends money. The one test that does is opt-in at the bottom.
"""

import pytest
from fastapi.testclient import TestClient

from app import config, db, explain, ratelimit
from app.main import app

client = TestClient(app)


# --------------------------------------------------------------------------
# Mock mode, through the endpoint
# --------------------------------------------------------------------------


def test_every_known_camera_gets_an_explanation():
    body = client.post("/explanations", json={"camera_ids": [1, 3, 8]}).json()
    explanations = body["explanations"]
    assert set(explanations) == {"1", "3", "8"}
    assert all(len(text) > 30 for text in explanations.values())


def test_explanations_match_the_camera_type():
    explanations = client.post(
        "/explanations", json={"camera_ids": [1, 3]}
    ).json()["explanations"]
    assert "plate reader" in explanations["1"]
    assert "speed" in explanations["3"].lower()


def test_unknown_ids_are_left_out_rather_than_failing_the_batch():
    body = client.post("/explanations", json={"camera_ids": [1, 999]}).json()
    assert set(body["explanations"]) == {"1"}


def test_an_empty_or_oversized_batch_is_refused():
    assert client.post("/explanations", json={"camera_ids": []}).status_code == 422
    too_many = list(range(1, 32))
    assert (
        client.post("/explanations", json={"camera_ids": too_many}).status_code
        == 422
    )


# --------------------------------------------------------------------------
# Guards, same posture as the other billed endpoints
# --------------------------------------------------------------------------


def test_the_allowance_runs_out():
    for _ in range(6):
        assert (
            client.post("/explanations", json={"camera_ids": [1]}).status_code
            == 200
        )
    refused = client.post("/explanations", json={"camera_ids": [1]})
    assert refused.status_code == 429
    assert int(refused.headers["Retry-After"]) >= 1
    assert refused.json()["detail"]


def test_explanations_spend_their_own_allowance():
    """Exhausting explanations must not close planning: they are separate
    bills and a driver mid-trip still needs their route."""
    for _ in range(7):
        client.post("/explanations", json={"camera_ids": [1]})
    trip = {
        "origin": {"lat": 38.9696, "lng": -77.3861},
        "destination": {"lat": 38.8462, "lng": -77.3064},
    }
    assert client.post("/plan", json=trip).status_code == 200


def test_a_missing_key_is_refused_when_a_key_is_set(monkeypatch):
    monkeypatch.setattr(config, "APP_KEY", "s3cret")
    ratelimit.reset()
    assert client.post("/explanations", json={"camera_ids": [1]}).status_code == 401
    keyed = client.post(
        "/explanations", json={"camera_ids": [1]}, headers={"X-App-Key": "s3cret"}
    )
    assert keyed.status_code == 200


# --------------------------------------------------------------------------
# The real path, with Claude stubbed out
# --------------------------------------------------------------------------

# Rows as _CAMERAS_FOR_EXPLAIN returns them: id, type, facing_deg, operator,
# brand, road_name, road_ref, road_class, maxspeed, crime_count, crime_desc,
# tract_income, county_income, arrest_count, arrest_desc, usefulness_score,
# score_desc, explanation.
EXPLAINED_ROW = (
    1, "alpr", 90.0, "Fairfax County Police Department", "Flock Safety",
    "Lee Highway", "US 29", "primary", "45 mph",
    4, "reported incidents within half a mile in the last 12 months (DC MPD)",
    142500, 98000,
    120, "arrests recorded in police service area 208 in 2025 (DC MPD)",
    23, "scored on 3 of 3 factors",
    "Already written.",
)
BARE_ROW = (
    2, "alpr", None, None, None, None, None, None, None,
    None, None, None, None, None, None, None, None, None,
)


@pytest.fixture
def real_explain(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCK_EXPLAIN", False)
    saved = []
    monkeypatch.setattr(db, "save_explanation", lambda cid, text: saved.append((cid, text)))
    return saved


def test_a_cached_row_is_served_without_a_claude_call(real_explain, monkeypatch):
    monkeypatch.setattr(db, "fetch_cameras_for_explain", lambda ids: [EXPLAINED_ROW])

    def no_call(row):
        raise AssertionError("a cached camera must not be regenerated")

    monkeypatch.setattr(explain, "_generate_one", no_call)
    assert explain.explanations_for([1]) == {1: "Already written."}
    assert real_explain == []


def test_a_miss_is_generated_once_and_saved(real_explain, monkeypatch):
    monkeypatch.setattr(
        db, "fetch_cameras_for_explain", lambda ids: [EXPLAINED_ROW, BARE_ROW]
    )
    monkeypatch.setattr(explain, "_generate_one", lambda row: "Freshly written.")

    result = explain.explanations_for([1, 2])
    assert result == {1: "Already written.", 2: "Freshly written."}
    assert real_explain == [(2, "Freshly written.")]


def test_one_failure_does_not_cost_the_rest(real_explain, monkeypatch):
    monkeypatch.setattr(
        db, "fetch_cameras_for_explain", lambda ids: [EXPLAINED_ROW, BARE_ROW]
    )
    monkeypatch.setattr(explain, "_generate_one", lambda row: None)

    assert explain.explanations_for([1, 2]) == {1: "Already written."}
    assert real_explain == []


def test_total_failure_is_a_503(real_explain, monkeypatch):
    monkeypatch.setattr(db, "fetch_cameras_for_explain", lambda ids: [BARE_ROW])
    monkeypatch.setattr(explain, "_generate_one", lambda row: None)

    response = client.post("/explanations", json={"camera_ids": [2]})
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


def test_facts_omit_what_we_do_not_know():
    """A "Operator: None" line invites the model to invent one."""
    facts = explain._facts(BARE_ROW)
    assert "None" not in facts
    assert "license plate reader" in facts
    # No region line either: the table spans states, and a hardcoded one
    # taught Claude to misplace a Delaware camera in Virginia.
    assert "Region" not in facts

    full = explain._facts(EXPLAINED_ROW)
    assert "Lee Highway (US 29)" in full
    assert "45 mph" in full
    assert "Computed usefulness score: 23/100 (scored on 3 of 3 factors)" in full
    assert "Crime near this camera: 4 reported incidents" in full
    assert "Arrests: 120 arrests recorded in police service area 208" in full
    assert "$142,500 (county median $98,000)" in full


# --------------------------------------------------------------------------
# Live, opt-in, billed
# --------------------------------------------------------------------------


@pytest.mark.skipif(
    config.ANTHROPIC_API_KEY == "", reason="needs ANTHROPIC_API_KEY; billed"
)
def test_claude_actually_answers(monkeypatch):
    monkeypatch.setattr(config, "USE_MOCK_EXPLAIN", False)
    text = explain._generate_one(EXPLAINED_ROW[:17] + (None,))
    assert text is not None
    assert text.count(".") >= 1
    # The brief is two sentences, 40 words. Slack for the model counting
    # loosely, but a paragraph means the prompt regressed.
    assert len(text.split()) <= 65, text
