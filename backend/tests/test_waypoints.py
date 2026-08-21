from app.geo import haversine_m, point_to_polyline_m, resample
from app.waypoints import (
    DIVERGENCE_THRESHOLD_M,
    MAX_WAYPOINTS,
    MAX_WAYPOINTS_STRICT,
    SPAN_CAMERA_RADIUS_M,
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


def cameras_on(route, indexes):
    """A camera sitting on the route at each given sample.

    Spans only earn a waypoint when a camera we are dodging is nearby, so
    a test about span handling has to put cameras where the spans are.
    """
    return [route[i] for i in indexes]


def test_identical_routes_have_no_waypoints():
    route = straight_route()
    assert pick_waypoints(route, route, cameras_on(route, [20])).waypoints == []


def test_no_waypoints_when_there_is_nothing_to_avoid():
    """Our route and Google's differ for reasons unrelated to cameras.

    The two engines prefer different roads, so there are almost always
    divergence spans. Steering Google through them when no camera is
    involved costs time and buys nothing.
    """
    baseline = straight_route()
    ours = bumped_route([(10, 20)])
    assert find_divergence_spans(ours, baseline, []), "there is a span here"
    assert pick_waypoints(ours, baseline, []).waypoints == []


def test_a_span_far_from_every_camera_is_ignored():
    baseline = straight_route()
    ours = bumped_route([(10, 20)])
    far_away = [(38.5, -77.0)]
    spans = find_divergence_spans(ours, baseline, far_away)
    assert spans[0].nearest_camera_m > SPAN_CAMERA_RADIUS_M
    assert pick_waypoints(ours, baseline, far_away).waypoints == []


def test_one_waypoint_per_divergence_span():
    baseline = straight_route()
    ours = bumped_route([(10, 20), (40, 50)])
    cameras = cameras_on(ours, [15, 45])
    assert len(find_divergence_spans(ours, baseline, cameras)) == 2
    assert len(pick_waypoints(ours, baseline, cameras).waypoints) == 2


def test_waypoint_sits_on_its_span_and_off_the_baseline():
    baseline = straight_route()
    ours = bumped_route([(10, 20)])
    waypoint = pick_waypoints(ours, baseline, cameras_on(ours, [15])).waypoints[0]
    assert point_to_polyline_m((waypoint.lat, waypoint.lng), ours) < 1
    assert point_to_polyline_m((waypoint.lat, waypoint.lng), baseline) > DIVERGENCE_THRESHOLD_M


def test_capped_closest_to_cameras_first():
    baseline = straight_route()
    ranges = [(i, i + 4) for i in range(5, 125, 10)]  # 12 spans
    ours = bumped_route(ranges)

    # A camera near every span, each a little further off than the last, so
    # the ordering the cap depends on is well defined. All well inside
    # SPAN_CAMERA_RADIUS_M, so the cap is what does the dropping.
    cameras = [
        (ours[start][0] + 0.0002 * i, ours[start][1]) for i, (start, _) in enumerate(ranges)
    ]
    picked = pick_waypoints(ours, baseline, cameras).waypoints

    # A normal plan keeps few, because each waypoint is a visible stop in
    # Google Maps and the ones furthest from a camera earn theirs least.
    assert len(picked) == MAX_WAYPOINTS
    kept = [(p.lat, p.lng) for p in picked]
    for start, _ in ranges[MAX_WAYPOINTS:]:
        assert not any(haversine_m(k, ours[start]) < 200 for k in kept)

    # Avoiding at any cost spends the whole budget Google allows.
    strict = pick_waypoints(ours, baseline, cameras, strict=True).waypoints
    assert len(strict) == MAX_WAYPOINTS_STRICT
    assert MAX_WAYPOINTS_STRICT > MAX_WAYPOINTS


def test_waypoints_are_returned_in_travel_order():
    baseline = straight_route()
    ours = bumped_route([(10, 20), (40, 50), (70, 80)])
    picked = pick_waypoints(ours, baseline, cameras_on(ours, [15, 45, 75])).waypoints
    assert len(picked) == 3
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

    picked = pick_waypoints(ours, baseline, cameras_on(ours, [15]), shortcutting_directions)
    assert len(calls) == 2
    assert len(picked.waypoints) == 1


def test_a_validated_pick_carries_the_route_google_will_drive():
    """The driver drives Google's route, so that is what gets checked."""
    baseline = straight_route()
    ours = bumped_route([(10, 20)])

    def cooperative(origin, waypoints, destination):
        return ours, 660

    picked = pick_waypoints(ours, baseline, cameras_on(ours, [15]), cooperative)
    assert picked.route == ours
    assert picked.eta_seconds == 660
