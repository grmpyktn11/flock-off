"""Shared types.

Camera lives here rather than in mock_data or db so both can build one,
and nothing downstream has to know which source a camera came from.
"""

from dataclasses import dataclass


@dataclass
class Camera:
    id: int
    osm_id: int
    type: str
    lat: float
    lng: float
    facing_deg: float | None
    # Context from OSM, present when the mapper recorded it: who runs the
    # camera, whose product it is, and the road it watches.
    operator: str | None = None
    brand: str | None = None
    road_name: str | None = None
    road_ref: str | None = None
