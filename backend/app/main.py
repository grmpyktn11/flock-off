"""FastAPI app: the three endpoints from the spec.

Cameras, Valhalla and the Google APIs are mocked in app.mock_data so this
service can be built and tested on its own.
"""

from fastapi import FastAPI, Query

from app import mock_data
from app.planner import plan_route
from app.schemas import PlanRequest, PlanResponse, ReplanRequest, SearchResponse

app = FastAPI(title="Camera-avoiding navigation backend")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(min_length=1),
    lat: float | None = None,
    lng: float | None = None,
) -> SearchResponse:
    """Places Autocomplete proxy. lat/lng bias results toward the driver."""
    return SearchResponse(results=mock_data.search_places(q, lat, lng))


@app.post("/plan", response_model=PlanResponse)
def plan(request: PlanRequest) -> PlanResponse:
    return plan_route(
        (request.origin.lat, request.origin.lng),
        (request.destination.lat, request.destination.lng),
    )


@app.post("/replan", response_model=PlanResponse)
def replan(request: ReplanRequest) -> PlanResponse:
    """Same pipeline as /plan, with the driver's current position as origin."""
    return plan_route(
        (request.current.lat, request.current.lng),
        (request.destination.lat, request.destination.lng),
    )
