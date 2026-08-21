"""FastAPI app: the three endpoints from the spec.

Cameras, Valhalla and the Google APIs are mocked in app.mock_data so this
service can be built and tested on its own.
"""

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from app import mock_data
from app.planner import plan_route
from app.schemas import PlanRequest, PlanResponse, ReplanRequest, SearchResponse
from app.valhalla import RoutingError

app = FastAPI(title="Camera-avoiding navigation backend")


@app.exception_handler(RoutingError)
def routing_unavailable(request: Request, exc: RoutingError) -> JSONResponse:
    """The routing engine is down or unreachable.

    The planner already survives a routing failure while avoiding cameras
    by falling back to the plain route. This is the case it cannot absorb:
    no baseline means no route at all, so there is nothing to hand the
    driver. 503 rather than 500 because the service is fine and its
    dependency is not, and because the app retries 5xx.
    """
    return JSONResponse(
        status_code=503,
        content={"detail": "Routing is temporarily unavailable. Try again shortly."},
    )


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
