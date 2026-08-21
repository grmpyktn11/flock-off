"""Valhalla routing.

The one thing only Valhalla can do is route around a polygon, which is
why it is here at all. Everything about the trip that the user sees -
the ETA, the route Google drives - comes from Google; see
docs/eta-delta.md for why Valhalla's own ETA is not shown to anyone.
"""

import requests

from app.config import VALHALLA_TIMEOUT_S, VALHALLA_URL
from app.geo import decode_polyline

# Valhalla encodes shapes at precision 6, not Google's 5.
SHAPE_PRECISION = 6


class RoutingError(RuntimeError):
    pass


def route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    exclude_rings: list[list[list[float]]] | None = None,
) -> tuple[list[tuple[float, float]], int]:
    """Return the route as (lat, lng) points and its duration in seconds.

    exclude_rings are [[lng, lat], ...] rings, the shape Valhalla wants and
    the shape ST_AsGeoJSON gives us.
    """
    body: dict = {
        "locations": [
            {"lat": origin[0], "lon": origin[1]},
            {"lat": destination[0], "lon": destination[1]},
        ],
        "costing": "auto",
    }
    if exclude_rings:
        body["exclude_polygons"] = exclude_rings

    try:
        response = requests.post(
            f"{VALHALLA_URL}/route", json=body, timeout=VALHALLA_TIMEOUT_S
        )
        response.raise_for_status()
        trip = response.json()["trip"]
    except requests.RequestException as cause:
        raise RoutingError(f"Valhalla did not answer: {cause}") from cause
    except (KeyError, ValueError) as cause:
        raise RoutingError(f"Valhalla sent something unexpected: {cause}") from cause

    points = decode_polyline(trip["legs"][0]["shape"], SHAPE_PRECISION)
    return points, round(trip["summary"]["time"])
