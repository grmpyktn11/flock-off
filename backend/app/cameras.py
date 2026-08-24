"""Camera lookups, from PostGIS or from the mock.

The two questions the planner asks are the same either way: which cameras
are near this trip, and which of them can see this route. Which source
answers is decided once, in app.config.
"""

import math

from app import config, db, mock_data
from app.config import BBOX_PADDING_M
from app.models import Camera


def in_bbox(
    origin: tuple[float, float], destination: tuple[float, float]
) -> list[Camera]:
    if config.USE_MOCK_CAMERAS:
        return mock_data.cameras_in_bbox(origin, destination, BBOX_PADDING_M)

    min_lat, min_lng, max_lat, max_lng = _padded_bbox(origin, destination)
    return [
        Camera(
            id=r[0], osm_id=r[1], type=r[2], lat=r[3], lng=r[4], facing_deg=r[5],
            operator=r[6], brand=r[7], road_name=r[8], road_ref=r[9],
        )
        for r in db.fetch_cameras_in_bbox(min_lng, min_lat, max_lng, max_lat)
    ]


def seen_by(route: list[tuple[float, float]], cameras: list[Camera]) -> set[int]:
    """Ids of the cameras whose dead zone this route passes through.

    Against PostGIS this is ST_Intersects on the stored dead zone, which is
    directional: a camera pointed away from the driver does not see them.
    The mock uses a plain radius and cannot express that, so it flags more
    cameras than the real check will.
    """
    if config.USE_MOCK_CAMERAS:
        return mock_data.ids_seeing_route(cameras, route)
    return db.fetch_ids_seeing_route([c.id for c in cameras], db.route_wkt(route))


def _padded_bbox(
    origin: tuple[float, float], destination: tuple[float, float]
) -> tuple[float, float, float, float]:
    pad_lat = BBOX_PADDING_M / 111320.0
    mid_lat = (origin[0] + destination[0]) / 2
    pad_lng = BBOX_PADDING_M / (111320.0 * math.cos(math.radians(mid_lat)))
    return (
        min(origin[0], destination[0]) - pad_lat,
        min(origin[1], destination[1]) - pad_lng,
        max(origin[0], destination[0]) + pad_lat,
        max(origin[1], destination[1]) + pad_lng,
    )
