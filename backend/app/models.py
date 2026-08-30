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
    # Public-records enrichment and the computed usefulness score, filled
    # by ingestion/enrich.py where jurisdictions publish the data. The
    # app renders these as the camera's factor breakdown.
    crime_count: int | None = None
    crime_desc: str | None = None
    arrest_count: int | None = None
    arrest_desc: str | None = None
    tract_income: int | None = None
    county_income: int | None = None
    usefulness_score: int | None = None
    score_desc: str | None = None
