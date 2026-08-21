# Camera-Avoiding Navigation - Final Spec

## What this is

An Android app (iOS/CarPlay planned for later) that plans driving routes
avoiding Flock ALPR and fixed speed cameras, then hands the route to
Google Maps as waypoints so Google does the actual turn-by-turn
navigation, including on Android Auto. The app runs in the background
giving audio alerts for any unavoidable cameras, and offers a one-tap
re-plan if Google's live rerouting takes the user off the planned path.

Test region: Fairfax / Herndon, Virginia (Nova area).

## Philosophy

- Extremely simple code. If there are two ways to do something, pick the
  boring one.
- Readability over cleverness, always.
- No over-engineering. Do not build for a feature that does not exist yet.
- Comments explain why, not what.
- No emojis anywhere: code, comments, commits, UI copy.
- Build for 1k-10k users eventually: cache external calls, keep keys
  server-side, index the database, connection pool. Nothing beyond that
  until it's an actual bottleneck.

## Full stack (final)

- **App**: React Native + Expo. NativeWind (Tailwind) + React Native Paper.
- **Backend**: Python + FastAPI.
- **Database**: Postgres + PostGIS.
- **Routing engine**: Valhalla, self-hosted (Docker), regional OSM extract
  (Fairfax/Herndon area to start).
- **Infra**: single EC2 instance running Valhalla + FastAPI backend
  together. Managed Postgres alongside it (Supabase or Neon), not on the
  same box, to protect against data loss.
- **External APIs**: Google Places (search/autocomplete, with session
  tokens), Google Directions (baseline route comparison), Overpass API
  (camera source data).
- **Distribution**: Android — direct APK via EAS Build initially, Play
  Store planned once community-scale (one-time $25 Play Console fee, no
  recurring cost). iOS — deferred, TestFlight (not raw sideloading) is
  the realistic path when it happens, since iOS has no APK equivalent.

## Key terms

- **OSM**: OpenStreetMap, the open map dataset everything is sourced from.
- **Overpass API**: query engine for pulling tagged data (cameras) out of OSM.
- **PostGIS**: Postgres extension adding geographic types and spatial
  math (distance, buffering, intersection) directly into SQL.
- **Valhalla**: open-source, self-hostable routing engine. Computes
  driving routes and supports excluding polygons from the path.
- **Dead zone**: the buffered road-segment polygon around a camera that
  a route must avoid to not be seen by it.

## The full pipeline

### Standing infrastructure
- Daily Overpass ingestion job pulls `man_made=surveillance` +
  `surveillance:type=ALPR` nodes and `highway=speed_camera` nodes for
  the region, reading both `camera:direction` and legacy `direction`
  tags. Upserts into a `cameras` table (id, osm_id, type, geom, facing_deg,
  dead_zone, first_seen, last_seen, active).
- Dead zone geometry computed once at ingestion, not per request:
  - Snap camera to nearest road (PostGIS nearest-neighbor via spatial index)
  - If facing known: clip a 75ft segment of the road in that direction
    (`ST_LineSubstring`), buffer to road width (`ST_Buffer`)
  - If unknown: buffer 75ft both directions from the camera point
- Valhalla runs continuously on the EC2 box with the regional OSM extract
  loaded.

### Per-trip flow
1. **Search**: app sends keystrokes to backend, backend proxies to Google
   Places Autocomplete (session token), returns matches.
2. **Plan** (`POST /plan`, origin + destination):
   - Fetch cameras in a bounding box around the trip (PostGIS)
   - Get Google's default route + ETA (traffic-aware, for comparison)
   - Call Valhalla with `exclude_polygons` = dead zones, get avoidance route
   - Verify: check the returned route against dead zones (`ST_DWithin`),
     retry with adjusted exclusions if violations remain (max 2 retries)
   - ETA honesty check: compare avoidance route ETA vs baseline, surface
     the delta to the user
   - Waypoint picking: walk both polylines together at regular intervals,
     find divergence spans (where the two routes disagree), place one
     waypoint per span (max 9, prioritized by proximity to cameras being
     avoided), validate against Google Directions, adjust if needed
   - Return: deep link URL, camera list, avoided/unavoidable counts,
     ETA delta, our route polyline (for drift detection)
3. **Launch**: app starts a foreground service (required for background
   GPS on Android), stores the plan locally, fires the Google Maps deep
   link (`https://www.google.com/maps/dir/?api=1&origin=..&destination=..&waypoints=..&travelmode=driving`)
4. **Drive** (all local, no network, every ~2s GPS tick):
   - Proximity: haversine distance to nearest unavoidable camera; alert
     via TTS through car audio if within a speed-adjusted threshold
   - Drift: point-to-line-segment distance from current position to our
     stored route; 100m+ for 3 consecutive ticks triggers an off-route
     notification with a one-tap re-plan (`POST /replan`)
5. **End**: near destination, manual end, or long stationary period stops
   the foreground service.

## Math inventory

| Step | Concept | Who computes it |
|---|---|---|
| Snap camera to road | Nearest-neighbor spatial search | PostGIS |
| Dead zone shape | Line clipping + buffering | PostGIS |
| Route calculation | Graph pathfinding (Dijkstra/A*-family) | Valhalla |
| Route verification | Distance-within-polygon check | PostGIS |
| Waypoint picking | Polyline divergence comparison | Backend, custom |
| Live proximity alerts | Haversine distance | Phone, local |
| Drift detection | Point-to-line-segment distance | Phone, local |

## Backend endpoints

- `GET /search?q=&lat=&lng=` — Places Autocomplete proxy
- `POST /plan` — full planning pipeline, returns deep link + metadata
- `POST /replan` — same pipeline from current position
- Ingestion job is internal (scheduled task, not an endpoint)

## Explicitly out of scope for now

- iOS/CarPlay build (planned, not started; revisit Apple's CarPlay
  navigation entitlement application early since approval time varies)
- User accounts beyond lightweight auth (needed once community-scale,
  not needed for the POC or early testing)
- Crowdsourced live police reporting (no automated data source exists)
- Microservices, queues, multi-region hosting, read replicas — not
  justified at any scale discussed so far

## Build order

1. **POC** (one Claude Code session or a couple parallel instances):
   Overpass ingestion script, dead zone buffer function, waypoint-picker
   function, all testable from the command line against the Fairfax/
   Herndon area. Manually confirm a Google Maps deep link with hand-
   picked waypoints actually holds the route around a known camera.
2. **~100 users**: full stack above, direct APK, basic version of every
   endpoint and screen, no caching or optimization yet.
3. **~1k-10k users**: connection pooling, plan-result caching, Play Store
   migration, no new architecture, just hardening.

## Parallelizing with Claude Code

Use git worktrees to run independent pieces in separate Claude Code
instances at once:
- Ingestion + dead zone math (Python, PostGIS)
- Backend API + waypoint picker (FastAPI, can build against mocked data)
- App shell (React Native, can build against a mocked backend response)

Merge to main once each piece works standalone. Use subagents within a
single session for self-contained sub-tasks that would otherwise clutter
the main context.
