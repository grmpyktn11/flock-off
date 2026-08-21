from app.geo import haversine_m, point_to_polyline_m, resample
from app.waypoints import (
    DIVERGENCE_THRESHOLD_M,
    MAX_WAYPOINTS,
    find_divergence_spans,
    pick_waypoints,
)

ORIGIN = (38.9696, -77.3861)
DESTINATION = (38.8462, -77.3064)


def straight_route():
    return resample([ORIGIN, DESTINATION], 100.0)


def bumped_route(bump_ranges, offset_deg=0.004):
    """Straight route with the given sample ranges pushed sideways."""
    route = straight_route()
    return [
        (lat, lng + offset_deg) if any(a <= i < b for a, b in bump_ranges) else (lat, lng)
        for i, (lat, lng) in enumerate(route)
    ]


def test_identical_routes_have_no_waypoints():
    route = straight_route()
    assert pick_waypoints(route, route, []).waypoints == []


def test_one_waypoint_per_divergence_span():
    baseline = straight_route()
    ours = bumped_route([(10, 20), (40, 50)])
    assert len(find_divergence_spans(ours, baseline, [])) == 2
    assert len(pick_waypoints(ours, baseline, []).waypoints) == 2


def test_waypoint_sits_on_its_span_and_off_the_baseline():
    baseline = straight_route()
    ours = bumped_route([(10, 20)])
    waypoint = pick_waypoints(ours, baseline, []).waypoints[0]
    assert point_to_polyline_m((waypoint.lat, waypoint.lng), ours) < 1
    assert point_to_polyline_m((waypoint.lat, waypoint.lng), baseline) > DIVERGENCE_THRESHOLD_M


def test_capped_at_nine_waypoints_closest_to_cameras_first():
    baseline = straight_route()
    ranges = [(i, i + 4) for i in range(5, 125, 10)]  # 12 spans
    ours = bumped_route(ranges)
    far_span, near_span = ours[5:9], ours[115:119]
    cameras = [near_span[0]]
    picked = pick_waypoints(ours, baseline, cameras).waypoints

    assert len(picked) == MAX_WAYPOINTS
    kept = [(w.lat, w.lng) for w in picked]
    assert any(haversine_m(p, near_span[0]) < 500 for p in kept)
    assert not any(haversine_m(p, far_span[0]) < 500 for p in kept)


def test_waypoints_are_returned_in_travel_order():
    baseline = straight_route()
    ours = bumped_route([(10, 20), (40, 50), (70, 80)])
    picked = pick_waypoints(ours, baseline, [DESTINATION]).waypoints
    distances = [haversine_m(ORIGIN, (w.lat, w.lng)) for w in picked]
    assert distances == sorted(distances)


def test_validation_adjusts_a_waypoint_google_shortcuts_past():
    baseline = straight_route()
    ours = bumped_route([(10, 20)])

    calls = []

    def shortcutting_directions(origin, waypoints, destination):
        calls.append(waypoints)
        # The Routes API reports the duration alongside the path.
        return (baseline, 600) if len(calls) == 1 else (ours, 660)

    picked = pick_waypoints(ours, baseline, [], shortcutting_directions).waypoints
    assert len(calls) == 2
    assert len(picked) == 1
