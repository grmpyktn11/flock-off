# Ingestion

Pulls cameras from OpenStreetMap, computes each one's dead zone, and
loads the `cameras` table.

## What it does

1. Queries Overpass for ALPR and speed camera nodes in a region, plus
   every drivable road within 60m of one.
2. Snaps each camera to its nearest road and builds a 75ft dead zone:
   - facing known: 75ft of road in that direction, buffered to road width
   - facing unknown or across the road: 75ft both ways
   - no road within 150ft: a 75ft circle
3. Upserts into Postgres (`ingestion/schema.sql`) or writes GeoJSON.

## Setup

    pip install -r requirements.txt

## Run

Offline, against bundled sample data:

    python -m ingestion.ingest --cameras-file ingestion/sample_cameras.json

Live Overpass, to GeoJSON (drop it on geojson.io to eyeball):

    python -m ingestion.ingest --region fairfax-herndon --out cameras.geojson

Live Overpass, into Postgres (apply `ingestion/schema.sql` first):

    python -m ingestion.ingest --region dmv --database-url postgresql://...

Regions live in `regions.json` at the repo root. See
`docs/adding-a-region.md`.

## Test

    python -m pytest tests -q

## Routing tiles

`infra/valhalla/` is the separate road-graph pipeline: built by hand from
OSM extracts every month or so, shipped to the server as one tarball.
See `infra/valhalla/build_tiles.md`.

## Scale notes

- Large regions are fetched as 2-degree tiles with backoff. DMV is ~2
  minutes nightly, fine for the public Overpass instance.
- Past one state, self-host Overpass or switch to Geofabrik extracts
  filtered with `osmium tags-filter`. Only `overpass.py` would change.
- Per-trip cost does not grow with the table: `/plan` queries by trip
  bounding box.

## Known gaps

- Road width is a flat 24ft.
- `sample_roads.geojson` exists only for offline runs.
- OSM camera coverage is uneven. A low count means thin mapping, not no
  cameras.
