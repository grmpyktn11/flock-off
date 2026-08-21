"""Google Routes and Places.

Google does the actual navigating, so anything the driver is shown has to
be measured the way Google measures it. That is why the ETA both before
and after avoidance is priced here rather than taken from Valhalla; see
docs/eta-delta.md.

No key configured means the mock answers, same rule as the other sources.
"""

import requests

from app import config, mock_data
from app.geo import decode_polyline

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# Billing follows the field mask, so each call asks for the least it can.
# The ETA lookup needs no geometry at all.
_DURATION_ONLY = "routes.duration"
_DURATION_AND_SHAPE = "routes.duration,routes.polyline.encodedPolyline"


class GoogleError(RuntimeError):
    pass


def route_eta_seconds(
    origin: tuple[float, float],
    waypoints: list[tuple[float, float]],
    destination: tuple[float, float],
) -> int:
    """Seconds Google expects this trip to take, traffic included.

    With no waypoints this is the plain route the driver would otherwise
    have taken. With them it is our avoidance route, priced as the deep
    link will actually drive it - which is not the same path Valhalla
    produced, because Google routes between the waypoints its own way.
    """
    if config.USE_MOCK_GOOGLE:
        return mock_data.google_route_eta(origin, waypoints, destination)
    return _compute_route(origin, waypoints, destination, _DURATION_ONLY)[1]


def directions(
    origin: tuple[float, float],
    waypoints: list[tuple[float, float]],
    destination: tuple[float, float],
) -> tuple[list[tuple[float, float]], int]:
    """The path Google would drive, and how long it takes.

    Used to validate the waypoint picks. The duration comes back in the
    same response, so pricing our avoidance route costs no extra call as
    long as the picks survive validation unchanged.
    """
    if config.USE_MOCK_GOOGLE:
        return mock_data.google_directions(origin, waypoints, destination)
    return _compute_route(origin, waypoints, destination, _DURATION_AND_SHAPE)


def search_places(
    query: str, lat: float | None, lng: float | None, session_token: str | None = None
) -> list[dict]:
    """Places Autocomplete.

    session_token groups a burst of keystrokes and the Place Details call
    that follows into one billable session. The app generates one per
    search and drops it once a place is chosen.
    """
    if config.USE_MOCK_GOOGLE:
        return mock_data.search_places(query, lat, lng)
    raise NotImplementedError("Places API (New) call lands with the key")


def _compute_route(
    origin: tuple[float, float],
    waypoints: list[tuple[float, float]],
    destination: tuple[float, float],
    field_mask: str,
) -> tuple[list[tuple[float, float]], int]:
    """One Routes API call. Returns (points, seconds); points may be empty.

    Intermediates are left as stopovers rather than marked `via`, because
    that is what the deep link's `waypoints=` parameter produces in Google
    Maps. Pricing a pass-through route would time a trip nobody drives.
    """
    body = {
        "origin": _waypoint(origin),
        "destination": _waypoint(destination),
        "travelMode": "DRIVE",
        # TRAFFIC_AWARE, not TRAFFIC_AWARE_OPTIMAL: the cheaper tier, and
        # the difference does not show up in a minutes-level comparison.
        "routingPreference": "TRAFFIC_AWARE",
        "units": "METRIC",
    }
    if waypoints:
        body["intermediates"] = [_waypoint(w) for w in waypoints]

    try:
        response = requests.post(
            ROUTES_URL,
            json=body,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": config.GOOGLE_API_KEY,
                "X-Goog-FieldMask": field_mask,
            },
            timeout=config.GOOGLE_TIMEOUT_S,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as cause:
        raise GoogleError(f"Routes API did not answer: {cause}") from cause

    routes = payload.get("routes") or []
    if not routes:
        raise GoogleError("Routes API found no route")

    route = routes[0]
    # Durations come back as a protobuf duration string, "1234s".
    seconds = round(float(route["duration"].rstrip("s")))
    encoded = route.get("polyline", {}).get("encodedPolyline", "")
    points = decode_polyline(encoded) if encoded else []
    return points, seconds


def _waypoint(point: tuple[float, float]) -> dict:
    return {"location": {"latLng": {"latitude": point[0], "longitude": point[1]}}}
