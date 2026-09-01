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
    # Free generations granted by default, so tests about caching and
    # failure handling are not also tests about the allowance.
    monkeypatch.setattr(db, "claim_free_explain_use", lambda iid, limit: True)
    return saved


def test_a_cached_row_is_served_without_a_claude_call(real_explain, monkeypatch):
    monkeypatch.setattr(db, "fetch_cameras_for_explain", lambda ids: [EXPLAINED_ROW])

    def no_call(row, api_key):
        raise AssertionError("a cached camera must not be regenerated")

    monkeypatch.setattr(explain, "_generate_one", no_call)
    assert explain.explanations_for([1]) == {1: "Already written."}
    assert real_explain == []


def test_a_miss_is_generated_once_and_saved(real_explain, monkeypatch):
    monkeypatch.setattr(
        db, "fetch_cameras_for_explain", lambda ids: [EXPLAINED_ROW, BARE_ROW]
    )
    monkeypatch.setattr(explain, "_generate_one", lambda row, key: "Freshly written.")

    result = explain.explanations_for([1, 2], install_id="phone-a")
    assert result == {1: "Already written.", 2: "Freshly written."}
    assert real_explain == [(2, "Freshly written.")]


def test_one_failure_does_not_cost_the_rest(real_explain, monkeypatch):
    monkeypatch.setattr(
        db, "fetch_cameras_for_explain", lambda ids: [EXPLAINED_ROW, BARE_ROW]
    )
    monkeypatch.setattr(explain, "_generate_one", lambda row, key: None)

    result = explain.explanations_for([1, 2], install_id="phone-a")
    assert result == {1: "Already written."}
    assert real_explain == []


def test_total_failure_is_a_503(real_explain, monkeypatch):
    monkeypatch.setattr(db, "fetch_cameras_for_explain", lambda ids: [BARE_ROW])
    monkeypatch.setattr(explain, "_generate_one", lambda row, key: None)

    response = client.post(
        "/explanations",
        json={"camera_ids": [2]},
        headers={"X-Install-Id": "phone-a"},
    )
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


# --------------------------------------------------------------------------
# Whose key pays: the free allowance, then the user's own
# --------------------------------------------------------------------------


def test_a_users_key_is_the_one_used(real_explain, monkeypatch):
    monkeypatch.setattr(db, "fetch_cameras_for_explain", lambda ids: [BARE_ROW])
    keys_used = []

    def record_key(row, api_key):
        keys_used.append(api_key)
        return "Written on their dime."

    monkeypatch.setattr(explain, "_generate_one", record_key)
    monkeypatch.setattr(
        db,
        "claim_free_explain_use",
        lambda iid, limit: pytest.fail("a user key must not spend the allowance"),
    )

    result = explain.explanations_for([2], user_key="sk-ant-users-own")
    assert result == {2: "Written on their dime."}
    assert keys_used == ["sk-ant-users-own"]


def test_cached_rows_never_touch_the_allowance(real_explain, monkeypatch):
    monkeypatch.setattr(db, "fetch_cameras_for_explain", lambda ids: [EXPLAINED_ROW])
    monkeypatch.setattr(
        db,
        "claim_free_explain_use",
        lambda iid, limit: pytest.fail("a fully cached batch is free"),
    )
    assert explain.explanations_for([1], install_id="phone-a") == {
        1: "Already written."
    }


def test_a_spent_allowance_is_a_402_naming_the_fix(real_explain, monkeypatch):
    monkeypatch.setattr(db, "fetch_cameras_for_explain", lambda ids: [BARE_ROW])
    monkeypatch.setattr(db, "claim_free_explain_use", lambda iid, limit: False)

    response = client.post(
        "/explanations",
        json={"camera_ids": [2]},
        headers={"X-Install-Id": "phone-a"},
    )
    assert response.status_code == 402
    assert "Anthropic API key" in response.json()["detail"]


def test_no_install_id_means_no_free_tier(real_explain, monkeypatch):
    """A request without an install id is not the app; it gets no
    allowance rather than an uncountable infinite one."""
    monkeypatch.setattr(db, "fetch_cameras_for_explain", lambda ids: [BARE_ROW])
    monkeypatch.setattr(
        db,
        "claim_free_explain_use",
        lambda iid, limit: pytest.fail("nothing to count without an id"),
    )
    response = client.post("/explanations", json={"camera_ids": [2]})
    assert response.status_code == 402


def test_a_rejected_user_key_is_a_403_blaming_the_key(real_explain, monkeypatch):
    import anthropic
    import httpx

    monkeypatch.setattr(db, "fetch_cameras_for_explain", lambda ids: [BARE_ROW])

    def rejected(row, api_key):
        raise anthropic.AuthenticationError(
            "invalid x-api-key",
            response=httpx.Response(
                401, request=httpx.Request("POST", "https://api.anthropic.com")
            ),
            body=None,
        )

    monkeypatch.setattr(explain, "_generate_one", rejected)
    response = client.post(
        "/explanations",
        json={"camera_ids": [2]},
        headers={"X-Anthropic-Key": "sk-ant-wrong"},
    )
    assert response.status_code == 403
    assert "your API key" in response.json()["detail"]


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
    text = explain._generate_one(
        EXPLAINED_ROW[:17] + (None,), config.ANTHROPIC_API_KEY
    )
    assert text is not None
    assert text.count(".") >= 1
    # The brief is two sentences, 40 words. Slack for the model counting
    # loosely, but a paragraph means the prompt regressed.
    assert len(text.split()) <= 65, text
