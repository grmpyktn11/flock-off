"""Google Routes and Places.

Google does the actual navigating, so anything the driver is shown has to
be measured the way Google measures it. That is why the ETA both before
and after avoidance is priced here rather than taken from Valhalla; see
docs/eta-delta.md.

No key configured means the mock answers, same rule as the other sources.
"""

from app import config, mock_data


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
    raise NotImplementedError("Routes API call lands with the key")


def directions(
    origin: tuple[float, float],
    waypoints: list[tuple[float, float]],
    destination: tuple[float, float],
) -> list[tuple[float, float]]:
    """The path Google would drive, used to validate the waypoint picks."""
    if config.USE_MOCK_GOOGLE:
        return mock_data.google_directions(origin, waypoints, destination)
    raise NotImplementedError("Routes API call lands with the key")


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
