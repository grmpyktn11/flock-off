# Backend handoff notes

Branch: `feature/backend`. Scope built: the FastAPI service and the
waypoint picker, against mocked data sources. Ingestion and the app were
built in their own worktrees and are not touched here.

## State

- `GET /search`, `POST /plan`, `POST /replan`, `GET /health` all working
- Waypoint picker implemented per the spec's step 6
- 13 tests passing (`pytest`), server verified booting and serving
- Cameras, Valhalla, Google Directions and Google Places are all mocked in
  `app/mock_data.py` and nowhere else, so the real services land in one file

## Blocking at merge: the plan response contract

`mobile/src/api/types.ts` and this service disagree. Someone who owns
both sides has to pick one; the app maps its API layer or the backend
renames, either is a small change, but it will not work as-is.

| App expects | Backend returns |
|---|---|
| `deepLinkUrl` | `deep_link` |
| `avoidedCount` / `unavoidableCount` | `avoided_count` / `unavoidable_count` |
| `baselineEtaMinutes` / `avoidanceEtaMinutes` / `etaDeltaMinutes` | `baseline_eta_seconds` / `route_eta_seconds` / `eta_delta_seconds` |
| `routePolyline` | `route_polyline` |
| `Camera.id` string | `id` int |
| `Plan.origin` / `Plan.destination` echoed as `Place` | not returned |
| `Place { placeId, description }` | `{ place_id, name, address }` |

Recommendation: the backend keeps snake_case and seconds, and the app maps
in `src/api/` where `mockBackend.ts` already lives. Seconds rather than
minutes because rounding the ETA delta to whole minutes throws away the
number the user is being asked to accept. This is a recommendation, not a
decision - say which way and the backend conforms.

The app also has no `/replan` call yet, and ignores the `waypoints` array
the plan response includes. Neither breaks anything.

## Where the mock is cruder than reality, not just fake

`mock_data.camera_is_avoided` treats a camera as a 23m circle around its
point. The real dead zone from `ingestion/ingestion/deadzone.py` is a
directional polygon: a 75ft stretch of the snapped road clipped in the
camera's facing direction, buffered to road width. A camera facing away
from you does not see you, and a circle cannot express that.

So the verification step is directionally blind today. It becomes
`ST_Intersects(route, dead_zone)` once the table exists. Expect the avoided
and unavoidable counts to change when that lands - the current numbers are
pessimistic, since the circle flags cameras that are not actually watching
the driver's direction of travel.

Everything else mocked is only standing in for data, not for logic.

## Integration order

The database is the first shared dependency, and it is not useful to the
backend until it has rows in it:

1. Provision Postgres + PostGIS. Spec says managed (Neon or Supabase),
   separate from the EC2 box. `postgis/postgis` in Docker is fine locally.
2. Apply `ingestion/ingestion/schema.sql`.
3. Run the ingestion job with `--database-url` so `cameras` is populated.
4. Backend: replace `cameras_in_bbox` with a PostGIS bbox query filtered on
   `active = TRUE`, and `camera_is_avoided` with the dead zone intersect.
   The `Camera` model needs `dead_zone` and `active` added.
5. Backend: replace `valhalla_route` (exclude_polygons payload plus response
   decoding), `google_baseline_route` (traffic-aware ETA), and
   `search_places`.

Step 5's Places work includes session tokens, which the spec calls for and
this service does not have - there is no live API call to attach them to
yet. One token per keystroke burst, reused for the final Place Details
call, so Google bills the burst as one session.

Note that `schema.sql` currently exists only in the ingestion worktree. It
should end up somewhere both pieces can see it rather than being copied.

## Deliberately not built

Per the spec's build order, none of this is justified yet: caching, connection
pooling, auth, rate limiting. No API keys are handled anywhere in this branch.

## Running it

    pip install -r requirements.txt
    uvicorn app.main:app --reload
    pytest

If a globally installed pytest plugin breaks collection (hydra does this on
at least one dev machine), run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest`.
That is a local environment problem, not a repo one.

## Layout

- `app/main.py` - endpoints
- `app/planner.py` - pipeline: cameras, baseline route, avoidance route,
  verification retries, waypoints, deep link
- `app/waypoints.py` - the waypoint picker
- `app/geo.py` - polyline codec, haversine, point-to-segment, resampling
- `app/mock_data.py` - every stand-in, in one place
