"""Per-IP rate limits on the endpoints that cost money.

Every request this service serves turns into at least one billed Google
call, and the app carries no account to bill it to. An IP is the only
handle there is, so an IP is what gets counted.

slowapi does the counting. Three of its defaults are wrong for us and are
overridden below:

- **moving-window** rather than the default fixed window. A fixed window
  resets on the minute, so a scraper can send a full allowance at 12:00:59
  and another at 12:01:01 - twice the limit in two seconds, while
  technically obeying "30 a minute". A moving window counts the trailing
  sixty seconds and has no boundary to exploit.
- **headers_enabled** so a refusal carries `Retry-After`. Without it a
  client has nothing to wait on and retries immediately, which is the
  opposite of what a rate limit is for.
- **a `detail` body**, matching every other error this API returns, so the
  app's existing `failureMessage()` shows the driver a sentence instead of
  "The server answered 429."

Storage is this process's memory, which is right for one box and one
worker. Running uvicorn with --workers > 1 would give each worker its own
counters and silently multiply every limit; that needs a shared store
before it needs more workers.

The limits are deliberately loose. Mobile carriers put many subscribers
behind one public address, so a dozen strangers in Fairfax can share an
IP, and a limit tight enough to feel satisfying would lock them out of
each other's trips. Loose still costs a scraper everything, because what
it wants is thousands a minute, not thirty.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# get_remote_address reads request.client.host, which behind Caddy is the
# proxy unless uvicorn runs with --proxy-headers --forwarded-allow-ips
# 127.0.0.1. Without those flags every caller shares one counter and the
# first busy minute locks out everyone. The systemd unit in
# docs/deploying.md carries them; this is the line that depends on it.
limiter = Limiter(
    key_func=get_remote_address,
    strategy="moving-window",
    headers_enabled=True,
    retry_after="delta-seconds",
)

# /search is one call per keystroke burst and /place is the priciest single
# call Google bills us for. A driver spends a handful on one trip.
SEARCH_LIMIT = "30/minute"

# A plan is two to three Routes calls, and a re-plan is the same pipeline
# at the same cost - so they spend from one allowance rather than letting
# an address ask for twice as much by alternating.
PLAN_LIMIT = "10/minute"

# One batch covers a whole plan's cameras, so a driver needs one of these
# per trip. Tighter than the others because a cache miss inside a batch is
# a billed Claude call, and a scraper walking camera ids could otherwise
# pay to explain the whole table.
EXPLAIN_LIMIT = "6/minute"


def plan_limit():
    return limiter.shared_limit(PLAN_LIMIT, scope="plan")


def too_many_requests(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response = JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Give it a moment and try again."},
    )
    # slowapi's own pattern for a custom handler: build the response, then
    # let the limiter add Retry-After and the X-RateLimit-* headers.
    return request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )


def reset() -> None:
    """Drop all counters. For tests, which must not inherit each other's."""
    limiter.reset()
