"""Request and response models."""

from pydantic import BaseModel, Field


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class PlanRequest(BaseModel):
    origin: Point
    destination: Point
    # Optional, and only used to label the deep link. Google names a bare
    # coordinate after whatever it finds nearest, which is how "Tysons
    # Corner Center" arrives in the Maps app called "Default".
    origin_place_id: str | None = None
    destination_place_id: str | None = None


class ReplanRequest(BaseModel):
    """Same pipeline as /plan, started from where the driver is now."""

    current: Point
    destination: Point
    destination_place_id: str | None = None


class PlaceSuggestion(BaseModel):
    """One autocomplete suggestion. No coordinates.

    Resolving a location costs a Place Details call, so only the
    suggestion the driver actually picks gets one. See GET /place.
    """

    place_id: str
    name: str
    address: str


class SearchResponse(BaseModel):
    results: list[PlaceSuggestion]


class PlaceDetail(PlaceSuggestion):
    lat: float
    lng: float


class ExplainRequest(BaseModel):
    """The cameras of one plan. Capped because each unexplained camera is
    a billed Claude call, and no real plan crosses thirty cameras."""

    camera_ids: list[int] = Field(min_length=1, max_length=30)


class ExplainResponse(BaseModel):
    # Keyed by camera id. Unknown ids and failed generations are absent,
    # so the app shows what it got rather than nothing.
    explanations: dict[int, str]


class CameraResult(BaseModel):
    id: int
    type: str
    lat: float
    lng: float
    facing_deg: float | None
    avoided: bool
    operator: str | None = None
    brand: str | None = None
    road_name: str | None = None
    road_ref: str | None = None
    # The camera's public-records factors and computed usefulness score,
    # rendered by the app as a structured breakdown. Null where the
    # jurisdiction publishes nothing.
    crime_count: int | None = None
    crime_desc: str | None = None
    arrest_count: int | None = None
    arrest_desc: str | None = None
    tract_income: int | None = None
    county_income: int | None = None
    usefulness_score: int | None = None
    score_desc: str | None = None


class WaypointResult(BaseModel):
    lat: float
    lng: float
    nearest_camera_m: float


class PlanResponse(BaseModel):
    deep_link: str
    route_polyline: str
    waypoints: list[WaypointResult]
    cameras: list[CameraResult]
    avoided_count: int
    unavoidable_count: int
    baseline_eta_seconds: int
    route_eta_seconds: int
    eta_delta_seconds: int
