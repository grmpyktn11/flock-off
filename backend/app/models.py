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
