# Ingestion

Camera ingestion and dead zone math for the camera-avoiding navigation
backend. See `final-spec.md` for the whole system; this repo covers only
the standing ingestion job.

## What it does

1. Queries the Overpass API for `man_made=surveillance` +
   `surveillance:type=ALPR` nodes and `highway=speed_camera` nodes in a
   named region, reading both `camera:direction` and the legacy
   `direction` tag. The same query also returns every drivable road
   within 60m of a camera it found, so snapping needs no roads table.
2. Snaps each camera to its nearest road and computes a 75ft dead zone:
   - facing known: the 75ft of road the camera looks down, buffered to
     road width
   - facing unknown, or aimed across the road rather than along it: 75ft
     in both directions, buffered the same way
   - no road within 150ft: a plain 75ft circle around the camera
3. Upserts into the `cameras` table (`ingestion/schema.sql`), or writes
   GeoJSON so the result can be eyeballed on a map.

The geometry runs in Shapely against a projected CRS (UTM 18N, meters)
and mirrors the PostGIS calls the spec names, so it can be swapped for
`ST_ClosestPoint` / `ST_LineSubstring` / `ST_Buffer` once a real roads
table exists.

## Setup

    pip install -r requirements.txt

## Run

Offline, against the bundled fake cameras and hand-traced roads:

    python -m ingestion.ingest --cameras-file ingestion/sample_cameras.json

Live Overpass, writing GeoJSON:

    python -m ingestion.ingest --region fairfax-herndon --out cameras.geojson

Live Overpass, into Postgres (apply `ingestion/schema.sql` first):

    python -m ingestion.ingest --region virginia --database-url postgresql://...

Regions are defined in `ingestion/overpass.py`: `fairfax-herndon`,
`dmv`, `virginia`, `dc-ny`, `east-coast`.

Drop the GeoJSON onto geojson.io to check the dead zones sit on the
right side of the right roads.

## Test

    python -m pytest tests -q

## Routing tiles

`infra/valhalla/` holds the road-graph side, which is a separate pipeline from
the nightly camera ingestion above: built by hand every month or so from
OSM extracts, not from Overpass, and shipped to the server as a single
tarball.

- `infra/valhalla/build_tiles.md` -- the build procedure, including the clip
  and merge step that is not optional, and measured timings
- `infra/valhalla/build_progress.py` -- stage-by-stage progress of a running
  build, `--watch` to follow it
- `infra/valhalla/smoke_test.py` -- routes across the region, drops a real
  dead zone on that route, and checks the re-route avoids it

Verified against a live build of NoVa + DC + Maryland: 594 MB of tiles,
routes returned in under 400 ms, dead zones avoided.

This directory is here because the dead zone code it tests lives here.
It arguably belongs with the backend or in an infra repo; worth moving
when these branches merge.

## Scaling to a wider region

Anything past a metro area is split into 2-degree tiles, fetched one at
a time with backoff, and deduplicated. Measured on the public Overpass
instance:

| region | cameras | roads | snapped | wall time |
|---|---|---|---|---|
| Fairfax/Herndon | 350 | 2,818 | 99.4% | 8s |
| DMV, NoVa+DC+MD (3 tiles) | 2,872 | 19,231 | 99.7% | 2min |
| Virginia (10 tiles) | 5,133 | 33,219 | 99.7% | 8min |
| DC-NY corridor | 8,116 | - | - | - |
| East coast (108 tiles) | 40,546 | - | - | ~1-1.5h projected |

`dmv` is the intended serving region: 2,872 cameras (2,439 ALPR, 433
speed cameras), 84% of them with a usable facing bearing, 3.3 MB of
GeoJSON. A two-minute nightly job well within Overpass etiquette, and a
table small enough that no part of the spec's single-box design is
strained.

So the whole east coast is roughly 40k cameras and an hour of nightly
Overpass time. That is a fine size for Postgres and for the ingestion
job. Two things do not come for free at that scale:

- **Overpass etiquette.** An hour of queries against the free public
  instance every night is impolite and will get throttled (we already
  hit 429s while measuring). Past one state, either self-host Overpass
  or switch the source to nightly Geofabrik extracts filtered with
  `osmium tags-filter`, which has no rate limits and is more reliable.
  The parsing in `overpass.py` is the only part that would change.
- **Valhalla, not this repo.** Routing tiles for the whole east coast
  are far larger than the Fairfax extract the spec assumes, and the
  single EC2 box in the spec is sized for one metro. Ingestion reaching
  east-coast scale does not mean the router can. Widen the camera
  region only as far as the routing extract actually covers.

Per-trip cost does not grow: `/plan` pulls dead zones for a trip
bounding box, not the whole table.

## Known gaps

- Road width is a flat 24ft. OSM `lanes` and `width` tags could refine
  it; not worth it until dead zones prove too tight or too wide in
  practice.
- `ingestion/sample_roads.geojson` is four hand-traced roads and exists
  only so `--cameras-file` runs offline. Live runs use the roads
  Overpass returns.
- Camera coverage in OSM is uneven. Northern Virginia is well mapped
  because of DeFlock-style community mapping; other regions are not, and
  a low camera count for an area means thin data, not no cameras.
