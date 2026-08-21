"""The planning pipeline (spec: per-trip flow, step 2).

Fetch cameras, get a baseline route, get an avoidance route, verify it,
pick waypoints, and build the Google Maps deep link.
"""

from urllib.parse import urlencode

from app import cameras as camera_source
from app import google, routing
from app.valhalla import RoutingError
from app.geo import encode_polyline
from app.models import Camera
from app.schemas import CameraResult, PlanResponse, WaypointResult
from app.waypoints import pick_waypoints

MAX_VERIFY_RETRIES = 2

# How much wider to make the exclusions when a route still clips one. A
# dead zone is a 75ft road slice buffered to road width, about 23m by 7m,
# so this only has to push the route off the edge of that. It was 100m,
# which is four times the length of the thing being avoided: three of
# those stacked around a suburban corridor sealed the road network and
# Valhalla answered "no path could be found".
EXCLUSION_EXPAND_STEP_M = 15.0

DEEP_LINK_BASE = "https://www.google.com/maps/dir/"


def plan_route(origin: tuple[float, float], destination: tuple[float, float]) -> PlanResponse:
    cameras = camera_source.in_bbox(origin, destination)
    baseline_route, _ = routing.baseline_route(origin, destination)
    # The cameras that would see the driver on the route they would
    # otherwise have taken. These are the ones worth routing around, and
    # the only ones that can be "avoided" in any meaningful sense - the
    # bounding box also returns cameras kilometers off the trip, and
    # counting those would claim credit for every camera in the county.
    baseline_ids = camera_source.seen_by(baseline_route, cameras)

    route, unavoidable_ids = _route_avoiding(
        origin, destination, cameras, baseline_ids, baseline_route
    )
    avoided_ids = baseline_ids - unavoidable_ids
    reported = [c for c in cameras if c.id in avoided_ids or c.id in unavoidable_ids]
    avoided = [c for c in reported if c.id in avoided_ids]

    picked = pick_waypoints(
        route,
        baseline_route,
        [(c.lat, c.lng) for c in avoided],
        google.directions,
    )
    waypoints = picked.waypoints
    picks = [(w.lat, w.lng) for w in waypoints]

    # Both ETAs come from Google, and the second one prices the route the
    # deep link will actually drive rather than the one Valhalla planned.
    # Google routes between our waypoints its own way, so those are
    # different paths. Comparing Valhalla's avoidance ETA against Google's
    # baseline would report the gap between two routing engines as if it
    # were the cost of dodging a camera - see docs/eta-delta.md.
    # Validating the picks already priced them, so the usual path costs one
    # Google call, not two. picked.eta_seconds is only None when the picks
    # changed after the last validation call, which is the uncommon case.
    baseline_eta = google.route_eta_seconds(origin, [], destination)
    if not picks:
        route_eta = baseline_eta
    elif picked.eta_seconds is not None:
        route_eta = picked.eta_seconds
    else:
        route_eta = google.route_eta_seconds(origin, picks, destination)

    return PlanResponse(
        deep_link=build_deep_link(origin, picks, destination),
        route_polyline=encode_polyline(route),
        waypoints=[
            WaypointResult(lat=w.lat, lng=w.lng, nearest_camera_m=round(w.nearest_camera_m, 1))
            for w in waypoints
        ],
        cameras=[
            CameraResult(
                id=c.id,
                type=c.type,
                lat=c.lat,
                lng=c.lng,
                facing_deg=c.facing_deg,
                avoided=c.id in avoided_ids,
            )
            for c in reported
        ],
        avoided_count=len(avoided_ids),
        unavoidable_count=len(unavoidable_ids),
        baseline_eta_seconds=baseline_eta,
        route_eta_seconds=route_eta,
        eta_delta_seconds=route_eta - baseline_eta,
    )


def _route_avoiding(
    origin: tuple[float, float],
    destination: tuple[float, float],
    cameras: list[Camera],
    exclude_ids: set[int],
    fallback: list[tuple[float, float]],
) -> tuple[list[tuple[float, float]], set[int]]:
    """Route around the dead zones, retrying while the result still hits any.

    Two things can go wrong on an attempt, and the retry handles both. The
    detour can run into a camera that was not on the original route, which
    is fixed by adding it to the exclusion set. Or the route can clip a
    zone it was already told to avoid by hugging its edge, which is fixed
    by widening the exclusions.

    Some cameras cannot be avoided at all, for instance one sitting on the
    only road out of the origin, so we stop retrying and report them.

    fallback is the route to use if avoidance cannot produce one, which
    happens when the exclusions close off every way through. A route that
    passes a camera the driver is warned about beats no route at all.

    Only the geometry is returned. Valhalla's duration is not used
    anywhere: the ETAs the driver sees are priced by Google, because
    Google is what drives the trip. See docs/eta-delta.md.
    """
    expand_m = 0.0
    excluded = set(exclude_ids)
    best: tuple[list[tuple[float, float]], set[int]] | None = None

    for attempt in range(MAX_VERIFY_RETRIES + 1):
        avoid = [c for c in cameras if c.id in excluded]
        try:
            route, _ = routing.avoidance_route(origin, destination, avoid, expand_m)
        except RoutingError:
            # Widening the exclusions can seal the network. Keep whatever
            # the last attempt managed rather than failing the trip.
            break

        unavoidable_ids = camera_source.seen_by(route, cameras)
        best = (route, unavoidable_ids)
        if not unavoidable_ids or attempt == MAX_VERIFY_RETRIES:
            break
        excluded |= unavoidable_ids
        expand_m += EXCLUSION_EXPAND_STEP_M

    if best is None:
        # Not even the first attempt routed. Report the plain route, with
        # every camera on it called unavoidable, because it is.
        return fallback, camera_source.seen_by(fallback, cameras)
    return best


def build_deep_link(
    origin: tuple[float, float],
    waypoints: list[tuple[float, float]],
    destination: tuple[float, float],
) -> str:
    params = {
        "api": "1",
        "origin": _format_point(origin),
        "destination": _format_point(destination),
        "travelmode": "driving",
    }
    if waypoints:
        params["waypoints"] = "|".join(_format_point(w) for w in waypoints)
    return DEEP_LINK_BASE + "?" + urlencode(params)


def _format_point(point: tuple[float, float]) -> str:
    return f"{point[0]:.6f},{point[1]:.6f}"
