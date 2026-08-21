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


def plan_route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    origin_place_id: str | None = None,
    destination_place_id: str | None = None,
) -> PlanResponse:
    cameras = camera_source.in_bbox(origin, destination)

    # The baseline is Google's route, not Valhalla's, and one call gives
    # us all three things we need from it: the geometry, for deciding
    # which cameras the driver would have passed and where our route
    # diverges from theirs, and the traffic-aware duration.
    #
    # It has to be Google's. The two engines pick genuinely different
    # roads - on one Fairfax trip, 26.6 km against 32.3 km - so waypoints
    # derived from Valhalla's baseline describe a detour from a route
    # Google was never going to drive, and handing them over drags it
    # kilometres off course.
    baseline_route, baseline_eta = google.directions(origin, [], destination)

    # The cameras that would see the driver on the route they would
    # otherwise have taken. These are the ones worth routing around, and
    # the only ones that can be "avoided" in any meaningful sense - the
    # bounding box also returns cameras kilometers off the trip, and
    # counting those would claim credit for every camera in the county.
    baseline_ids = camera_source.seen_by(baseline_route, cameras)

    route, _ = _route_avoiding(origin, destination, cameras, baseline_ids, baseline_route)

    picked = pick_waypoints(
        route,
        baseline_route,
        [(c.lat, c.lng) for c in cameras if c.id in baseline_ids],
        google.directions,
    )
    picks = [(w.lat, w.lng) for w in picked.waypoints]

    # What the driver actually drives. Valhalla proposes a route, but the
    # deep link hands Google waypoints and Google fills in the rest its own
    # way, so the cameras have to be checked against Google's answer. With
    # no waypoints the driver simply gets Google's plain route.
    #
    # Validating the picks already produced both that route and its
    # duration, so the usual trip costs no extra call.
    if not picks:
        driven_route, route_eta = baseline_route, baseline_eta
    elif picked.route is not None and picked.eta_seconds is not None:
        driven_route, route_eta = picked.route, picked.eta_seconds
    else:
        driven_route, route_eta = google.directions(origin, picks, destination)

    unavoidable_ids = camera_source.seen_by(driven_route, cameras)
    avoided_ids = baseline_ids - unavoidable_ids
    reported = [c for c in cameras if c.id in avoided_ids or c.id in unavoidable_ids]

    return PlanResponse(
        deep_link=build_deep_link(
            origin, picks, destination, origin_place_id, destination_place_id
        ),
        route_polyline=encode_polyline(driven_route),
        waypoints=[
            WaypointResult(lat=w.lat, lng=w.lng, nearest_camera_m=round(w.nearest_camera_m, 1))
            for w in picked.waypoints
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
    origin_place_id: str | None = None,
    destination_place_id: str | None = None,
) -> str:
    """The Google Maps URL the app hands over.

    Coordinates are what actually position the trip. A place id alongside
    them only changes the label: without one Google names the point after
    whatever it finds nearest, so a trip to Tysons Corner Center can open
    showing a business called "Default".

    The waypoints have no place ids and should not have any. They are
    points on a road chosen to hold a detour, not destinations.
    """
    params = {
        "api": "1",
        "origin": _format_point(origin),
        "destination": _format_point(destination),
        "travelmode": "driving",
    }
    if origin_place_id:
        params["origin_place_id"] = origin_place_id
    if destination_place_id:
        params["destination_place_id"] = destination_place_id
    if waypoints:
        params["waypoints"] = "|".join(_format_point(w) for w in waypoints)
    return DEEP_LINK_BASE + "?" + urlencode(params)


def _format_point(point: tuple[float, float]) -> str:
    return f"{point[0]:.6f},{point[1]:.6f}"
