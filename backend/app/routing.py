"""Route calculation, from Valhalla or from the mock.

Only the avoidance route goes through here. Valhalla is the only engine
that can route around a polygon, which is the sole reason it exists in
this system. The baseline is Google's and lives in app.google.
"""

from app import config, db, mock_data, valhalla
from app.models import Camera


def avoidance_route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    avoid: list[Camera],
    expand_m: float = 0.0,
) -> tuple[list[tuple[float, float]], int]:
    """Route from origin to destination, staying out of these dead zones.

    Only the cameras actually in the way belong in `avoid`. Valhalla caps
    the total circumference of exclude_polygons at 10000 metres, and a dead
    zone is about 60 metres around, so roughly 166 of them fit in one
    request - fewer than the 169 a Fairfax-sized bounding box returns.
    Excluding cameras the route was never going near would spend that
    budget on nothing.

    expand_m widens the exclusions, which is how a failed verification asks
    for a wider berth on the next attempt.
    """
    if config.USE_MOCK_ROUTING:
        return mock_data.valhalla_route(origin, destination, avoid, expand_m)

    rings = db.fetch_dead_zone_rings([c.id for c in avoid], expand_m)
    return valhalla.route(origin, destination, rings)
