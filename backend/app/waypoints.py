"""Waypoint picker (spec pipeline step 6).

Walk our avoidance route and Google's baseline route together at regular
intervals, find the spans where the two disagree, and place one waypoint
per span. Google Maps deep links accept at most 9 waypoints, so when
there are more spans than that we keep the ones closest to the cameras we
are avoiding - those are the detours that actually matter.
"""

from dataclasses import dataclass

from app.geo import haversine_m, point_to_polyline_m, resample

SAMPLE_INTERVAL_M = 100.0
DIVERGENCE_THRESHOLD_M = 60.0

# A span only earns a waypoint if it happens near a camera we are dodging.
# Our route and Google's differ for reasons that have nothing to do with
# cameras - the two engines simply prefer different roads - and forcing
# Google through those points buys nothing and costs a great deal. Measured
# on one Fairfax trip: three spans, nearest avoided camera 1.5km, 5.4km and
# 7.2km away, together adding 23 minutes to avoid two cameras neither span
# went near.
SPAN_CAMERA_RADIUS_M = 500.0
# Google Maps deep links take at most nine waypoints, and every one of
# them shows in the app as a stop the driver appears to be heading for.
# Confirmed on a real handover: our waypoint arrived in Google's stop list
# as "Towers Crescent, Fashion Blvd", a road nobody is stopping at.
#
# So a normal plan keeps few. Real trips have needed 0 to 4, and each one
# past that buys less avoidance while adding another phantom stop.
# "Avoid at any cost" spends the whole budget, because holding the detour
# is the entire point of asking for it.
MAX_WAYPOINTS = 4
MAX_WAYPOINTS_STRICT = 9
VALIDATION_TOLERANCE_M = 150.0
MAX_ADJUSTMENTS = 2


@dataclass
class Span:
    """A stretch of our route that leaves the baseline route."""

    start_index: int
    end_index: int
    samples: list[tuple[float, float]]
    deviations_m: list[float]
    nearest_camera_m: float


@dataclass
class Picks:
    """The chosen waypoints, and Google's duration for them if we know it.

    eta_seconds is set when the validation call happened to price exactly
    these waypoints, which is the common case. It is None when there was
    no validation call, or when the picks were adjusted after the last
    one, and then the caller has to ask Google itself.
    """

    waypoints: list["Waypoint"]
    eta_seconds: int | None
    # The route Google said it would drive through these waypoints. This
    # is the one the driver actually takes, so it is what the cameras
    # should be checked against.
    route: list[tuple[float, float]] | None = None


@dataclass
class Waypoint:
    lat: float
    lng: float
    span_start_index: int
    deviation_m: float
    nearest_camera_m: float


def find_divergence_spans(
    our_route: list[tuple[float, float]],
    baseline_route: list[tuple[float, float]],
    camera_points: list[tuple[float, float]],
) -> list[Span]:
    """Sample our route and group the samples that stray from the baseline."""
    samples = resample(our_route, SAMPLE_INTERVAL_M)
    deviations = [point_to_polyline_m(p, baseline_route) for p in samples]

    spans: list[Span] = []
    current: list[int] = []
    for i, deviation in enumerate(deviations):
        if deviation > DIVERGENCE_THRESHOLD_M:
            current.append(i)
            continue
        if current:
            spans.append(_build_span(current, samples, deviations, camera_points))
            current = []
    if current:
        spans.append(_build_span(current, samples, deviations, camera_points))
    return spans


def _build_span(
    indexes: list[int],
    samples: list[tuple[float, float]],
    deviations: list[float],
    camera_points: list[tuple[float, float]],
) -> Span:
    span_samples = [samples[i] for i in indexes]
    return Span(
        start_index=indexes[0],
        end_index=indexes[-1],
        samples=span_samples,
        deviations_m=[deviations[i] for i in indexes],
        nearest_camera_m=_nearest_camera_m(span_samples, camera_points),
    )


def _nearest_camera_m(
    points: list[tuple[float, float]], camera_points: list[tuple[float, float]]
) -> float:
    if not camera_points:
        return float("inf")
    return min(haversine_m(p, c) for p in points for c in camera_points)


def _anchor(span: Span) -> Waypoint:
    """Pick the point in a span that is furthest from the baseline route.

    That point is the one Google is least likely to shortcut past, so it
    is the strongest single anchor for holding the detour.
    """
    best = max(range(len(span.samples)), key=lambda i: span.deviations_m[i])
    lat, lng = span.samples[best]
    return Waypoint(
        lat=lat,
        lng=lng,
        span_start_index=span.start_index,
        deviation_m=span.deviations_m[best],
        nearest_camera_m=span.nearest_camera_m,
    )


def pick_waypoints(
    our_route: list[tuple[float, float]],
    baseline_route: list[tuple[float, float]],
    camera_points: list[tuple[float, float]],
    directions_fn=None,
    strict: bool = False,
) -> Picks:
    """Return the waypoints holding the detour, in travel order.

    directions_fn, when given, is used to validate the picks: it takes the
    origin, the waypoints and the destination and returns the route Google
    would actually drive along with its duration. Spans whose waypoint
    fails validation are nudged to the middle of the span and rechecked.

    strict keeps every divergence span rather than only those near a
    camera, which pins Google to our route instead of letting it rejoin
    its own. It avoids more and costs more, sometimes a great deal more,
    because the two engines disagree about good roads for reasons that
    have nothing to do with cameras.
    """
    if not camera_points:
        # Nothing to dodge, so nothing to steer around. Google's own route
        # is the answer and the deep link should carry no waypoints.
        return Picks([], None)

    spans = find_divergence_spans(our_route, baseline_route, camera_points)
    if not strict:
        spans = [s for s in spans if s.nearest_camera_m <= SPAN_CAMERA_RADIUS_M]
    if not spans:
        return Picks([], None)

    # Closest-to-a-camera first, then keep travel order for the deep link.
    cap = MAX_WAYPOINTS_STRICT if strict else MAX_WAYPOINTS
    spans = sorted(spans, key=lambda s: s.nearest_camera_m)[:cap]
    spans = sorted(spans, key=lambda s: s.start_index)

    waypoints = [_anchor(span) for span in spans]
    if directions_fn is None:
        return Picks(waypoints, None)
    return _validate(waypoints, spans, our_route, directions_fn)


def _validate(
    waypoints: list[Waypoint],
    spans: list[Span],
    our_route: list[tuple[float, float]],
    directions_fn,
) -> Picks:
    """Drive the waypoints through Google and adjust any span it shortcuts.

    The duration is only handed back when the call that produced it priced
    the waypoints being returned. Once a span is adjusted, the last
    response describes a set of picks that no longer exists.
    """
    for _ in range(MAX_ADJUSTMENTS):
        google_route, eta_seconds = directions_fn(
            our_route[0], [(w.lat, w.lng) for w in waypoints], our_route[-1]
        )
        bad = [
            i
            for i, span in enumerate(spans)
            if _span_missed(span, google_route)
        ]
        if not bad:
            return Picks(waypoints, eta_seconds, google_route)
        for i in bad:
            waypoints[i] = _midpoint_waypoint(spans[i])
    return Picks(waypoints, None)


def _span_missed(span: Span, google_route: list[tuple[float, float]]) -> bool:
    """True if Google's route does not follow this span of our route."""
    return any(
        point_to_polyline_m(p, google_route) > VALIDATION_TOLERANCE_M
        for p in span.samples
    )


def _midpoint_waypoint(span: Span) -> Waypoint:
    middle = len(span.samples) // 2
    lat, lng = span.samples[middle]
    return Waypoint(
        lat=lat,
        lng=lng,
        span_start_index=span.start_index,
        deviation_m=span.deviations_m[middle],
        nearest_camera_m=span.nearest_camera_m,
    )
