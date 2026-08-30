import pytest
from fastapi.testclient import TestClient

from app.geo import decode_polyline, encode_polyline, point_to_polyline_m
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


def test_search_returns_no_coordinates():
    """Resolving a location costs a Place Details call each.

    Doing that for every suggestion on every keystroke would be the most
    expensive possible way to run autocomplete, so search returns names
    only and the chosen one is resolved through /place.
    """
    results = client.get("/search", params={"q": "metro"}).json()["results"]
    assert results
    assert all("lat" not in r and "lng" not in r for r in results)


def test_place_resolves_a_suggestion_to_coordinates():
    suggestion = client.get("/search", params={"q": "Vienna"}).json()["results"][0]
    body = client.get(
        "/place", params={"place_id": suggestion["place_id"], "session_token": "s1"}
    ).json()
    assert body["place_id"] == suggestion["place_id"]
    assert 38 < body["lat"] < 40
    assert -78 < body["lng"] < -76


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


def test_speed_cameras_are_reported_but_never_routed_around():
    """A speed camera matters only at speed and gets a spoken heads-up, so
    it must not cost the driver detour minutes. This trip runs the corridor
    between two ALPRs and crosses only mock camera 3, a speed camera:
    reported, unavoided, and no waypoints spent on it."""
    trip = {
        # Midpoints of the camera 2-3 and 3-4 corridor gaps, so the
        # straight route passes camera 3 alone.
        "origin": {"lat": 38.923325, "lng": -77.356215},
        "destination": {"lat": 38.904815, "lng": -77.34426},
    }
    body = client.post("/plan", json=trip).json()
    assert [c["type"] for c in body["cameras"]] == ["speed_camera"]
    assert body["avoided_count"] == 0
    assert body["unavoidable_count"] == 1
    assert body["waypoints"] == []
    assert body["eta_delta_seconds"] == 0


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


def test_a_detour_that_does_not_lower_the_reader_count_is_discarded(monkeypatch):
    """The whole point of the detour is fewer readers, always.

    Google honors waypoints loosely, so the route it actually drives can
    pass readers the baseline never did (measured on Vienna Metro-GMU:
    one dodged, three new). Here the picked "detour" is the baseline
    itself - zero improvement - and the plan must throw it away: plain
    route, no waypoints, nothing claimed as avoided.
    """
    from app import planner
    from app.waypoints import Picks, Waypoint

    origin = (TRIP["origin"]["lat"], TRIP["origin"]["lng"])
    destination = (TRIP["destination"]["lat"], TRIP["destination"]["lng"])
    baseline, baseline_eta = mock_data.google_baseline_route(origin, destination)

    def worthless_detour(our_route, baseline_route, camera_points, directions_fn=None):
        middle = baseline[len(baseline) // 2]
        return Picks(
            [Waypoint(middle[0], middle[1], 0, 0.0, 0.0)],
            baseline_eta + 300,
            baseline,
        )

    monkeypatch.setattr(planner, "pick_waypoints", worthless_detour)

    body = client.post("/plan", json=TRIP).json()
    assert body["waypoints"] == []
    assert "waypoints=" not in body["deep_link"]
    assert body["avoided_count"] == 0
    assert body["eta_delta_seconds"] == 0
    assert body["route_polyline"] == encode_polyline(baseline)


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


def test_a_trip_still_plans_when_valhalla_is_down(monkeypatch):
    """Losing the avoidance engine degrades the trip, it does not end it.

    The baseline, the ETA and the waypoint check all come from Google, so
    Valhalla being unreachable costs us the detour and nothing else. The
    driver gets the plain route with the cameras on it named, which is a
    worse trip but still a trip.
    """
    from app import planner
    from app.valhalla import RoutingError

    def unreachable(*args, **kwargs):
        raise RoutingError("Valhalla did not answer")

    monkeypatch.setattr(planner.routing, "avoidance_route", unreachable)

    body = client.post("/plan", json=TRIP).json()
    assert body["deep_link"].startswith("https://www.google.com/maps/dir/")
    assert body["avoided_count"] == 0
    assert body["unavoidable_count"] >= 1
    assert body["eta_delta_seconds"] == 0


def test_plan_answers_503_when_google_is_down(monkeypatch):
    """Google is the dependency with no fallback.

    No baseline, no ETA, and no way to check our waypoints. Answer 503 so
    the app can say so and retry, rather than 500 with a stack trace.
    """
    from app import planner
    from app.google import GoogleError

    def unreachable(*args, **kwargs):
        raise GoogleError("Routes API did not answer")

    monkeypatch.setattr(planner.google, "directions", unreachable)

    response = client.post("/plan", json=TRIP)
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_a_plan_prices_the_avoidance_route_without_a_second_call(monkeypatch):
    """The validation call already knows how long our route takes.

    Every Google Routes call is billed, so planning should cost one ETA
    lookup for the baseline rather than two. The picker routes its picks
    through Google to check Google will follow them, and that response
    carries the duration of exactly those picks.

    Google has to actually follow the picks for the duration to describe
    them, so this stubs a Google that does. The bundled mock never can:
    it draws straight legs between waypoints, which no bowed avoidance
    route matches, so validation always exhausts its adjustments and the
    saving never applies against mock data.
    """
    from app import planner
    from app.geo import decode_polyline

    eta_calls: list[list] = []

    def counting_eta(origin, waypoints, destination):
        eta_calls.append(list(waypoints))
        return 900

    plan_first = client.post("/plan", json=TRIP).json()
    ours = decode_polyline(plan_first["route_polyline"])
    real_directions = planner.google.directions

    def cooperative_directions(origin, waypoints, destination):
        if not waypoints:
            # The baseline call. Has to stay the real baseline, or there
            # is nothing for our route to diverge from.
            return real_directions(origin, waypoints, destination)
        # Given our picks, Google drives exactly our route, so every span
        # validates and the duration describes the picks being returned.
        return ours, 1234

    monkeypatch.setattr(planner.google, "route_eta_seconds", counting_eta)
    monkeypatch.setattr(planner.google, "directions", cooperative_directions)

    body = client.post("/plan", json=TRIP).json()
    assert body["waypoints"], "this trip is supposed to need waypoints"

    # No standalone ETA lookup at all. The baseline call and the
    # validation call each returned a duration alongside their geometry.
    assert eta_calls == []
    assert body["route_eta_seconds"] == 1234


def test_the_deep_link_labels_its_endpoints_when_given_place_ids():
    """Google names a bare coordinate after whatever it finds nearest.

    A real trip to Tysons Corner Center opened in Maps showing a business
    called "Default", because all the link carried was a lat and lng.
    """
    body = client.post(
        "/plan",
        json={**TRIP, "origin_place_id": "ChIJorigin", "destination_place_id": "ChIJdest"},
    ).json()
    assert "origin_place_id=ChIJorigin" in body["deep_link"]
    assert "destination_place_id=ChIJdest" in body["deep_link"]


def test_waypoints_carry_no_place_ids():
    """They are points on a road chosen to hold a detour, not places."""
    body = client.post("/plan", json=TRIP).json()
    assert body["waypoints"], "this trip is supposed to need waypoints"
    assert "waypoint_place_ids" not in body["deep_link"]


def test_a_camera_at_the_destination_does_not_lose_the_others(monkeypatch):
    """Measured on a real trip: a reader 13m from George Mason University.

    Excluding it makes the destination unreachable, Valhalla answers "no
    path", and the plan used to fall back to the plain route - losing the
    avoidance for a second camera more than a kilometre away that had
    nothing to do with it.
    """
    from app import planner
    from app.models import Camera

    origin, destination = (38.90, -77.40), (38.86, -77.32)
    at_the_end = Camera(id=99, osm_id=99, type="alpr", lat=destination[0],
                        lng=destination[1], facing_deg=None)
    down_the_road = Camera(id=98, osm_id=98, type="alpr", lat=38.88, lng=-77.36,
                           facing_deg=None)

    stuck = planner._cameras_at_the_ends([at_the_end, down_the_road], origin, destination)
    assert stuck == {99}, "only the camera at the endpoint is unavoidable by position"


def test_every_span_is_held_by_default():
    """The plan pins Google to our route instead of letting it rejoin its
    own. Avoiding every camera that can possibly be avoided is the
    default and only behavior, whatever the detour costs.
    """
    from app.geo import resample
    from app.waypoints import pick_waypoints

    baseline = resample([(38.9696, -77.3861), (38.8462, -77.3064)], 100.0)
    ours = [
        (lat, lng + 0.004) if 10 <= i < 20 else (lat, lng)
        for i, (lat, lng) in enumerate(baseline)
    ]
    far_from_any_camera = [(38.5, -77.0)]

    assert pick_waypoints(ours, baseline, far_from_any_camera).waypoints
