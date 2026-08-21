"""Request and response models."""

from pydantic import BaseModel, Field


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class PlanRequest(BaseModel):
    origin: Point
    destination: Point


class ReplanRequest(BaseModel):
    """Same pipeline as /plan, started from where the driver is now."""

    current: Point
    destination: Point


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


class CameraResult(BaseModel):
    id: int
    type: str
    lat: float
    lng: float
    facing_deg: float | None
    avoided: bool


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
