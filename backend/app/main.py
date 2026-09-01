"""FastAPI app: the three endpoints from the spec.

Each data source falls back to app.mock_data when it is not configured,
so this service runs with no infrastructure at all and each real one can
be switched on independently.
"""

import logging

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app import google
from app.appkey import require_app_key
from app.explain import (
    BadUserKeyError,
    ExplainError,
    NeedsKeyError,
    explanations_for,
)
from app.google import GoogleError
from app.planner import plan_route
from app.ratelimit import (
    EXPLAIN_LIMIT,
    SEARCH_LIMIT,
    limiter,
    plan_limit,
    too_many_requests,
)
from app.schemas import (
    ExplainRequest,
    ExplainResponse,
    PlaceDetail,
    PlanRequest,
    PlanResponse,
    ReplanRequest,
    SearchResponse,
)
from app.valhalla import RoutingError

app = FastAPI(title="Camera-avoiding navigation backend")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, too_many_requests)

_access = logging.getLogger("flockoff.access")


@app.middleware("http")
async def count_requests(request: Request, call_next):
    """Enough to notice abuse, and nothing more.

    Path, status and address. Deliberately not the body: the coordinates
    in a plan request are the one thing this service is careful not to
    remember, and an access log is exactly where they would quietly
    accumulate. What you want from this is a 429 rate climbing, or one
    address appearing a thousand times an hour - both visible from these
    three fields.

    systemd captures stdout, so `journalctl -u flock-off -f` is the live
    view.
    """
    response = await call_next(request)
    client = request.client.host if request.client else "-"
    _access.info("%s %s %s %s", client, request.method, request.url.path, response.status_code)
    return response


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


@app.exception_handler(ExplainError)
def explain_unavailable(request: Request, exc: ExplainError) -> JSONResponse:
    """Anthropic is down or out of quota and nothing could be generated.

    Only a total failure lands here: a batch that produced anything at all
    returns what it got. Same shape and reasoning as the handler above."""
    return JSONResponse(
        status_code=503,
        content={"detail": "Explanations are temporarily unavailable. Try again shortly."},
    )


@app.exception_handler(NeedsKeyError)
def needs_own_key(request: Request, exc: NeedsKeyError) -> JSONResponse:
    """The free generations are spent; new ones need the user's key.

    402 because it is literally about payment, and because the app treats
    4xx as not-retryable - retrying without a key cannot help. The detail
    is shown to the user as-is, so it says what to do, not what happened.
    """
    return JSONResponse(
        status_code=402,
        content={
            "detail": "The free AI explanations are used up on this "
            "device. Add your own Anthropic API key in settings to keep "
            "generating new ones."
        },
    )


@app.exception_handler(BadUserKeyError)
def user_key_rejected(request: Request, exc: BadUserKeyError) -> JSONResponse:
    """403, not 401: 401 here means the app key, and confusing the two
    would send someone debugging the wrong secret."""
    return JSONResponse(
        status_code=403,
        content={
            "detail": "Anthropic rejected your API key. Check it in "
            "settings - it should start with sk-ant-."
        },
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get(
    "/search",
    response_model=SearchResponse,
    dependencies=[Depends(require_app_key)],
)
# `request` is where the limiter reads the caller's address; `response` is
# where it writes the X-RateLimit-* headers. Both are framework plumbing -
# neither carries anything this endpoint looks at.
@limiter.limit(SEARCH_LIMIT)
def search(
    request: Request,
    response: Response,
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


@app.get(
    "/place",
    response_model=PlaceDetail,
    dependencies=[Depends(require_app_key)],
)
@limiter.limit(SEARCH_LIMIT)
def place(
    request: Request,
    response: Response,
    place_id: str = Query(min_length=1),
    session_token: str | None = None,
) -> PlaceDetail:
    """Resolve one suggestion to coordinates, once the driver has chosen it.

    Passing back the same session_token used for the search closes the
    session, so Google bills the whole keystroke burst plus this call as
    one rather than per request.
    """
    return PlaceDetail(**google.place_details(place_id, session_token))


@app.post(
    "/plan",
    response_model=PlanResponse,
    dependencies=[Depends(require_app_key)],
)
@plan_limit()
def plan(request: Request, response: Response, body: PlanRequest) -> PlanResponse:
    # `request` and `response` belong to the rate limiter. The plan is in
    # `body`, which had to be renamed off `request` to make room.
    return plan_route(
        (body.origin.lat, body.origin.lng),
        (body.destination.lat, body.destination.lng),
        body.origin_place_id,
        body.destination_place_id,
    )


@app.post(
    "/explanations",
    response_model=ExplainResponse,
    dependencies=[Depends(require_app_key)],
)
@limiter.limit(EXPLAIN_LIMIT)
def explanations(
    request: Request, response: Response, body: ExplainRequest
) -> ExplainResponse:
    """Why each of these cameras is plausibly where it is.

    One batch per plan. Cameras already explained are served from their
    row; the rest cost one Claude call each, paid once ever - on the
    user's own key when X-Anthropic-Key comes along, otherwise on the
    server's key against the install's free allowance. The user's key is
    used for the one batch and never stored or logged."""
    return ExplainResponse(
        explanations=explanations_for(
            body.camera_ids,
            user_key=request.headers.get("x-anthropic-key", "").strip(),
            install_id=request.headers.get("x-install-id", "").strip(),
        )
    )


@app.post(
    "/replan",
    response_model=PlanResponse,
    dependencies=[Depends(require_app_key)],
)
@plan_limit()
def replan(request: Request, response: Response, body: ReplanRequest) -> PlanResponse:
    """Same pipeline as /plan, with the driver's current position as origin."""
    return plan_route(
        (body.current.lat, body.current.lng),
        (body.destination.lat, body.destination.lng),
        None,
        body.destination_place_id,
    )
