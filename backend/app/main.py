"""FastAPI app: the three endpoints from the spec.

Each data source falls back to app.mock_data when it is not configured,
so this service runs with no infrastructure at all and each real one can
be switched on independently.
"""

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from app import google
from app.planner import plan_route
from app.schemas import (
    PlaceDetail,
    PlanRequest,
    PlanResponse,
    ReplanRequest,
    SearchResponse,
)
from app.google import GoogleError
from app.valhalla import RoutingError

app = FastAPI(title="Camera-avoiding navigation backend")


@app.exception_handler(GoogleError)
@app.exception_handler(RoutingError)
def upstream_unavailable(request: Request, exc: Exception) -> JSONResponse:
    """An engine we depend on is down or unreachable.

    In practice this means Google. Valhalla failing is survivable: the
    planner falls back to Google's plain route and reports the cameras on
    it as unavoidable, which is a worse trip but still a trip. Google
    failing leaves no baseline, no ETA and no way to check our waypoints,
    so there is nothing to hand the driver.

    503 rather than 500 because this service is fine and its dependency is
    not, and because the app already treats 5xx as worth retrying.
    """
    return JSONResponse(
        status_code=503,
        content={"detail": "Route planning is temporarily unavailable. Try again shortly."},
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(min_length=1),
    lat: float | None = None,
    lng: float | None = None,
    session_token: str | None = None,
) -> SearchResponse:
    """Places Autocomplete proxy. lat/lng bias results toward the driver.

    session_token groups a burst of keystrokes and the Place Details call
    that follows into one billable session, which is how Google expects
    autocomplete to be used. The app generates one per search and drops it
    once a place is chosen.
    """
    return SearchResponse(results=google.search_places(q, lat, lng, session_token))


@app.get("/place", response_model=PlaceDetail)
def place(place_id: str = Query(min_length=1), session_token: str | None = None) -> PlaceDetail:
    """Resolve one suggestion to coordinates, once the driver has chosen it.

    Passing back the same session_token used for the search closes the
    session, so Google bills the whole keystroke burst plus this call as
    one rather than per request.
    """
    return PlaceDetail(**google.place_details(place_id, session_token))


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
