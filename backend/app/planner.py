"""The planning pipeline (spec: per-trip flow, step 2).

Fetch cameras, get a baseline route, get an avoidance route, verify it,
pick waypoints, and build the Google Maps deep link.
"""

from urllib.parse import urlencode

from app import mock_data
from app.geo import encode_polyline
from app.schemas import CameraResult, PlanResponse, WaypointResult
from app.waypoints import pick_waypoints

MAX_VERIFY_RETRIES = 2
EXCLUSION_EXPAND_STEP_M = 100.0

DEEP_LINK_BASE = "https://www.google.com/maps/dir/"


def plan_route(origin: tuple[float, float], destination: tuple[float, float]) -> PlanResponse:
    cameras = mock_data.cameras_in_bbox(origin, destination)
    baseline_route, baseline_eta = mock_data.google_baseline_route(origin, destination)
    route, route_eta, unavoidable = _route_avoiding(origin, destination, cameras)

    # A camera is only avoided if the normal route would have driven into
    # its dead zone and ours does not. The bounding box also returns
    # cameras kilometers off the trip, and counting those as avoided would
    # claim credit for every camera in the county.
    avoided = [
        c for c in cameras
        if _sees(c, baseline_route) and c not in unavoidable
    ]
    reported = [c for c in cameras if c in avoided or c in unavoidable]

    waypoints = pick_waypoints(
        route,
        baseline_route,
        [(c.lat, c.lng) for c in avoided],
        mock_data.google_directions,
    )

    return PlanResponse(
        deep_link=build_deep_link(origin, [(w.lat, w.lng) for w in waypoints], destination),
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
                avoided=c in avoided,
            )
            for c in reported
        ],
        avoided_count=len(avoided),
        unavoidable_count=len(unavoidable),
        baseline_eta_seconds=baseline_eta,
        route_eta_seconds=route_eta,
        eta_delta_seconds=route_eta - baseline_eta,
    )


def _sees(camera: mock_data.Camera, route: list[tuple[float, float]]) -> bool:
    """True if the route passes through this camera's dead zone."""
    return not mock_data.camera_is_avoided(camera, route)


def _route_avoiding(
    origin: tuple[float, float],
    destination: tuple[float, float],
    cameras: list[mock_data.Camera],
) -> tuple[list[tuple[float, float]], int, list[mock_data.Camera]]:
    """Route around the cameras, widening the exclusions while any remain.

    Some cameras cannot be avoided at all, for instance one sitting on the
    only road out of the origin, so we stop retrying and report them.
    """
    expand_m = 0.0
    for attempt in range(MAX_VERIFY_RETRIES + 1):
        route, eta = mock_data.valhalla_route(origin, destination, cameras, expand_m)
        unavoidable = [c for c in cameras if _sees(c, route)]
        if not unavoidable or attempt == MAX_VERIFY_RETRIES:
            return route, eta, unavoidable
        expand_m += EXCLUSION_EXPAND_STEP_M
    raise AssertionError("unreachable")


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
