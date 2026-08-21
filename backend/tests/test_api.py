import pytest
from fastapi.testclient import TestClient

from app.geo import decode_polyline, point_to_polyline_m
from app.main import app
from app import cameras as camera_source
from app import mock_data
from app.mock_data import DEAD_ZONE_RADIUS_M
from app.waypoints import MAX_WAYPOINTS

client = TestClient(app)

TRIP = {
    "origin": {"lat": 38.9696, "lng": -77.3861},
    "destination": {"lat": 38.8462, "lng": -77.3064},
}


def test_search_matches_by_name_and_biases_by_location():
    response = client.get("/search", params={"q": "metro", "lat": 38.88, "lng": -77.27})
    assert response.status_code == 200
    names = [r["name"] for r in response.json()["results"]]
    assert names == ["Vienna Metro Station", "Herndon Metro Station"]


def test_search_requires_a_query():
    assert client.get("/search", params={"q": ""}).status_code == 422


def test_plan_returns_a_usable_deep_link():
    body = client.post("/plan", json=TRIP).json()
    assert body["deep_link"].startswith("https://www.google.com/maps/dir/?api=1")
    assert "travelmode=driving" in body["deep_link"]
    assert 0 < len(body["waypoints"]) <= MAX_WAYPOINTS


def test_plan_route_clears_every_camera_it_reports_as_avoided():
    body = client.post("/plan", json=TRIP).json()
    route = decode_polyline(body["route_polyline"])
    for camera in body["cameras"]:
        distance = point_to_polyline_m((camera["lat"], camera["lng"]), route)
        assert (distance > DEAD_ZONE_RADIUS_M) == camera["avoided"]


def test_plan_counts_and_eta_delta_are_consistent():
    body = client.post("/plan", json=TRIP).json()
    assert body["avoided_count"] + body["unavoidable_count"] == len(body["cameras"])
    assert body["unavoidable_count"] >= 1  # sample camera 7 sits on the origin
    assert (
        body["eta_delta_seconds"]
        == body["route_eta_seconds"] - body["baseline_eta_seconds"]
    )
    assert body["eta_delta_seconds"] > 0


def test_replan_from_a_midpoint_matches_a_plan_from_the_same_point():
    midpoint = {"lat": 38.9079, "lng": -77.3462}
    replanned = client.post(
        "/replan", json={"current": midpoint, "destination": TRIP["destination"]}
    ).json()
    planned = client.post(
        "/plan", json={"origin": midpoint, "destination": TRIP["destination"]}
    ).json()
    assert replanned == planned


def test_plan_only_reports_cameras_that_saw_one_of_the_two_routes():
    """Cameras far off the trip are scenery, not avoidance wins.

    The bounding box is deliberately generous - a real Fairfax trip pulls
    a few hundred cameras - so without this the avoided count grows with
    the size of the box rather than with the work the route actually did.
    """
    origin = (TRIP["origin"]["lat"], TRIP["origin"]["lng"])
    destination = (TRIP["destination"]["lat"], TRIP["destination"]["lng"])
    baseline, _ = mock_data.google_baseline_route(origin, destination)

    body = client.post("/plan", json=TRIP).json()
    ours = decode_polyline(body["route_polyline"])
    assert body["cameras"], "this trip is supposed to have cameras on it"

    for camera in body["cameras"]:
        point = (camera["lat"], camera["lng"])
        on_baseline = point_to_polyline_m(point, baseline) <= DEAD_ZONE_RADIUS_M
        on_ours = point_to_polyline_m(point, ours) <= DEAD_ZONE_RADIUS_M
        assert on_baseline or on_ours
        assert camera["avoided"] == (on_baseline and not on_ours)

    in_bbox = camera_source.in_bbox(origin, destination)
    assert len(body["cameras"]) < len(in_bbox), "bbox cameras should be filtered down"


def test_plan_of_a_trip_with_no_cameras_is_a_plain_google_route():
    quiet = {
        "origin": {"lat": 38.9470, "lng": -77.3930},
        "destination": {"lat": 38.8611, "lng": -77.3760},
    }
    body = client.post("/plan", json=quiet).json()
    assert body["cameras"] == []
    assert body["avoided_count"] == 0
    assert body["waypoints"] == []
    assert "waypoints=" not in body["deep_link"]
    # No detour means no cost. Both ETAs price the same Google route, so
    # this is exactly zero rather than merely small.
    assert body["eta_delta_seconds"] == 0
    assert body["route_eta_seconds"] == body["baseline_eta_seconds"]


def test_plan_rejects_an_impossible_coordinate():
    bad = {"origin": {"lat": 200.0, "lng": 0.0}, "destination": TRIP["destination"]}
    assert client.post("/plan", json=bad).status_code == 422


def test_a_trip_still_plans_when_avoidance_cannot_route(monkeypatch):
    """Our own exclusions can seal off every way through.

    Widening a dead zone far enough makes Valhalla answer "no path could be
    found", which is a real 400 seen on a Fairfax corridor. The driver
    still needs to get there, so the plan falls back to the plain route
    and calls the cameras on it unavoidable rather than failing the trip.
    """
    from app import planner
    from app.valhalla import RoutingError

    def cannot_route(*args, **kwargs):
        raise RoutingError("no path could be found for input")

    monkeypatch.setattr(planner.routing, "avoidance_route", cannot_route)

    response = client.post("/plan", json=TRIP)
    assert response.status_code == 200
    body = response.json()
    assert body["deep_link"].startswith("https://www.google.com/maps/dir/")
    assert body["avoided_count"] == 0, "nothing was avoided, because nothing routed"
    assert body["unavoidable_count"] >= 1
    assert all(c["avoided"] is False for c in body["cameras"])


def test_plan_answers_503_when_the_routing_engine_is_down():
    """A dependency being unreachable is not a bug in this service.

    The planner absorbs a routing failure during avoidance by falling back
    to the plain route, but a failed baseline leaves nothing to hand the
    driver. Answer 503 so the app can say so and retry, rather than 500
    with a stack trace.
    """
    from app import planner
    from app.valhalla import RoutingError

    def unreachable(*args, **kwargs):
        raise RoutingError("Valhalla did not answer")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(planner.routing, "baseline_route", unreachable)
    try:
        response = client.post("/plan", json=TRIP)
    finally:
        monkeypatch.undo()

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()
