from fastapi.testclient import TestClient

from app.geo import decode_polyline, point_to_polyline_m
from app.main import app
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


def test_plan_rejects_an_impossible_coordinate():
    bad = {"origin": {"lat": 200.0, "lng": 0.0}, "destination": TRIP["destination"]}
    assert client.post("/plan", json=bad).status_code == 422
