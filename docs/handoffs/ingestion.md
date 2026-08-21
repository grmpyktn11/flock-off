# Handoff: feature/ingestion

Camera ingestion, dead zone geometry, and the Valhalla tile build.
Everything below was run against live services, not mocks. Numbers are
measured unless explicitly labelled an estimate.

Scope built: items 1 and 2 of the spec's POC build order. The waypoint
picker is not here; it lives in `feature/backend`.

## What is in this branch

    ingestion/overpass.py    Overpass queries, tiling, region definitions
    ingestion/deadzone.py    snap to road, 75ft dead zone geometry
    ingestion/ingest.py      CLI: Overpass -> dead zones -> Postgres or GeoJSON
    ingestion/schema.sql     cameras table, GIST indexes, upsert
    tests/                   19 tests
    valhalla/                tile build docs, progress viewer, smoke test
    README.md                usage, scaling table, known gaps

## Verified end to end

Against a real PostGIS 16 container:

- 2,872 live DMV cameras ingested in 131s (2,439 ALPR, 433 speed camera)
- upsert is idempotent: two runs of the same input leave the row count
  unchanged
- the deactivation sweep flips vanished cameras to `active = false` and
  preserves `first_seen`
- the `/plan` bounding box query uses the spatial index (`Bitmap Index
  Scan on cameras_geom_idx`), 358 cameras for a Fairfax-sized trip box
- whole table: 1.4 MB

Against a real Valhalla 3.5.1 instance built from OSM:

- dead zones produced by `ingestion.deadzone` are accepted as
  `exclude_polygons` and routed around
- Fairfax to Tysons: baseline 15.94 km crosses the dead zone, avoidance
  19.49 km does not
- Herndon to DC: baseline 39.95 km crosses, avoidance 39.66 km does not
- route latency 111-352 ms

## How to run it

    pip install -r requirements.txt

    # offline, no network, bundled fixtures
    python -m ingestion.ingest --cameras-file ingestion/sample_cameras.json

    # live, one region, to GeoJSON
    python -m ingestion.ingest --region dmv --out cameras.geojson

    # live, into Postgres (apply ingestion/schema.sql first)
    python -m ingestion.ingest --region dmv --database-url postgresql://...

    python -m pytest tests -q

Regions: `fairfax-herndon`, `dmv`, `virginia`, `dc-ny`, `east-coast`.

## Decisions worth knowing

**Roads come from Overpass, not a roads table.** The camera query also
returns every drivable way within 60m of a camera it found. That is a
few thousand ways for a town, and it removes the need for a roads table
entirely. Snap rate is 99.7% statewide. Before this, snapping was
effectively 0% because there was no road data to snap to.

**The dead zone is a clipped road segment, not a view cone.** The spec
says `ST_LineSubstring` plus `ST_Buffer`, and what a camera actually
watches is the road, not free space. The facing bearing decides which
way along the road to clip.

**Facing within 15 degrees of perpendicular is treated as unknown.** A
camera aimed across the road says nothing about which direction along it
the camera watches. Guessing would put the dead zone on the wrong side,
so those fall back to the both-directions buffer.

**Projection is per camera, not fixed.** Distances are computed in the
UTM zone the camera falls in. One zone spans 6 degrees of longitude, so
a region as wide as the east coast crosses three.

**Cameras are deactivated, never deleted.** That distinguishes a camera
that was removed from one never seen.

## Known gaps

- `ingestion/sample_roads.geojson` is four hand-traced roads. It exists
  only so the offline `--cameras-file` path runs without network. It is
  not real OSM geometry and nothing should be judged against it.
- Road width is a flat 24ft. OSM `lanes` and `width` could refine it,
  but not until dead zones prove wrong in practice.
- OSM camera coverage is uneven. Northern Virginia is well mapped
  because of community mapping; a thin count elsewhere means thin data,
  not an absence of cameras.
- `valhalla/` is in this repo because the dead zone code it exercises is
  here. It is really shared infra and probably belongs with the backend.

## Open questions for feature/backend

Neither is an ingestion problem, but both are load bearing for `/plan`.

**The waypoint picker never produced a waypoint.** A `/plan` call
returned six cameras marked avoided, zero waypoints, and a deep link
with no `waypoints=` parameter, meaning the link is an ordinary Google
route that avoids nothing. Most likely the mock's avoidance route does
not diverge from its baseline, so `pick_waypoints` correctly finds no
divergence spans. Worth confirming the mock produces a real detour,
because this is the only genuinely custom algorithm in the system and it
is currently unexercised.

**The avoidance route can score better than the baseline.** Excluding a
polygon returned a route that was both shorter and faster (10.00 km /
1036s versus 12.33 km / 1264s). A dummy polygon far out at sea did not
reproduce it, so it is not simply that any exclusion changes the search.
The likely cause is Valhalla disabling hierarchy shortcuts when an
exclusion is near the corridor, making the search more exhaustive. This
is a hypothesis, not a finding. It matters because the spec's ETA
honesty check would then be reporting an algorithm difference rather
than the real cost of avoiding cameras.

## Infrastructure

Scope the serving region to `dmv`. It is 2,872 cameras and a two minute
nightly Overpass job, which is polite enough for the free public
instance. The east coast is 40,546 cameras and roughly an hour nightly,
which would need a self-hosted Overpass or a switch to Geofabrik
extracts filtered with `osmium tags-filter`.

Sizing, measured rather than guessed:

| | |
|---|---|
| DMV routing tiles | 594 MiB (623 MB) |
| FastAPI backend RSS | 60 MB idle, no growth over 200 `/plan` calls |
| tile build peak RAM | 1.5 GB |
| tile build scratch disk | ~3 GB, deleted at cleanup |

A 4 GB box holds the tiles in page cache with room to spare. 1 GB does
not: the tile set alone would fill it and every route would hit disk.
Roughly 7.50 USD a month at the cheap end of the VPS market. Postgres
fits a free managed tier at this size.

Verify current pricing before committing; several providers changed
theirs in 2026.

## Environment note

The machine this was built on has a broken `hydra` pytest plugin
installed globally that crashes collection. Unrelated to this repo. Run
tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` on that machine only.
