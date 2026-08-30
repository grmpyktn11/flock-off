"""Camera ingestion job: Overpass -> dead zones -> Postgres (or GeoJSON).

Runnable offline against sample data:

    python -m ingestion.ingest --cameras-file ingestion/sample_cameras.json

One region, live (roads come back in the same query as the cameras):

    python -m ingestion.ingest --region fairfax-herndon --out cameras.geojson
    python -m ingestion.ingest --region east-coast --database-url postgresql://...
"""

import argparse
import json
import sys
import time

from ingestion import overpass
from ingestion.deadzone import RoadIndex, dead_zone_and_snap, load_roads

UPSERT_SQL = """
INSERT INTO cameras (osm_id, type, geom, facing_deg, dead_zone,
                     operator, brand, road_name, road_ref,
                     road_class, maxspeed)
VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s,
        ST_SetSRID(ST_GeomFromText(%s), 4326), %s, %s, %s, %s, %s, %s)
ON CONFLICT (osm_id) DO UPDATE SET
    type       = EXCLUDED.type,
    geom       = EXCLUDED.geom,
    facing_deg = EXCLUDED.facing_deg,
    dead_zone  = EXCLUDED.dead_zone,
    operator   = EXCLUDED.operator,
    brand      = EXCLUDED.brand,
    road_name  = EXCLUDED.road_name,
    road_ref   = EXCLUDED.road_ref,
    road_class = EXCLUDED.road_class,
    maxspeed   = EXCLUDED.maxspeed,
    last_seen  = now(),
    active     = TRUE;
"""

# Cameras that stopped coming back from Overpass are kept as history rather
# than deleted, so we can tell a removed camera from one we never saw.
DEACTIVATE_SQL = """
UPDATE cameras SET active = FALSE
WHERE active AND osm_id <> ALL(%s);
"""


def build_records(cameras, roads):
    index = RoadIndex(roads)
    for camera in cameras:
        dead_zone, road = dead_zone_and_snap(
            camera["lon"], camera["lat"], camera["facing_deg"], index
        )
        yield {
            **camera,
            "dead_zone": dead_zone,
            "snapped": road is not None,
            "road_name": road.name if road else None,
            "road_ref": road.ref if road else None,
            "road_class": road.road_class if road else None,
            "maxspeed": road.maxspeed if road else None,
        }


def write_geojson(records, stream):
    features = [
        {
            "type": "Feature",
            "properties": {
                "osm_id": r["osm_id"],
                "type": r["type"],
                "facing_deg": r["facing_deg"],
                "lon": r["lon"],
                "lat": r["lat"],
                "operator": r.get("operator"),
                "brand": r.get("brand"),
                "road_name": r.get("road_name"),
                "road_ref": r.get("road_ref"),
                "road_class": r.get("road_class"),
                "maxspeed": r.get("maxspeed"),
            },
            "geometry": r["dead_zone"].__geo_interface__,
        }
        for r in records
    ]
    json.dump({"type": "FeatureCollection", "features": features}, stream, indent=2)
    stream.write("\n")


def write_postgres(records, database_url, batch_size=1000):
    import psycopg

    rows = [
        (
            r["osm_id"],
            r["type"],
            r["lon"],
            r["lat"],
            r["facing_deg"],
            r["dead_zone"].wkt,
            r.get("operator"),
            r.get("brand"),
            r.get("road_name"),
            r.get("road_ref"),
            r.get("road_class"),
            r.get("maxspeed"),
        )
        for r in records
    ]
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for start in range(0, len(rows), batch_size):
                cur.executemany(UPSERT_SQL, rows[start : start + batch_size])
            cur.execute(DEACTIVATE_SQL, ([r[0] for r in rows],))
        # A bulk upsert leaves the planner's row estimates stale, and a bad
        # estimate on the bounding box query costs /plan a good plan. Cheap
        # on a table this size, so just do it every run.
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("ANALYZE cameras")
    return len(rows)


def load_cameras(path):
    with open(path) as f:
        return [overpass.parse_node(n) for n in json.load(f)["elements"]]


def report_tile(done, total, cameras, roads):
    print(
        f"tile {done}/{total}: {cameras} cameras, {roads} roads",
        file=sys.stderr,
        flush=True,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--region",
        default="fairfax-herndon",
        choices=sorted(overpass.REGIONS),
        help="named bounding box to ingest",
    )
    parser.add_argument(
        "--cameras-file",
        help="Overpass-shaped JSON to read instead of calling the live API",
    )
    parser.add_argument(
        "--roads",
        help="GeoJSON LineStrings to snap against; defaults to the roads "
        "Overpass returns alongside the cameras",
    )
    parser.add_argument("--database-url", help="Postgres URL; upsert instead of print")
    parser.add_argument("--out", help="Write GeoJSON here instead of stdout")
    args = parser.parse_args(argv)

    started = time.time()
    if args.cameras_file:
        cameras = load_cameras(args.cameras_file)
        roads = load_roads(args.roads or "ingestion/sample_roads.geojson")
    else:
        cameras, fetched = overpass.fetch(
            overpass.REGIONS[args.region], on_tile=report_tile
        )
        roads = load_roads(args.roads) if args.roads else fetched

    records = list(build_records(cameras, roads))
    snapped = sum(1 for r in records if r["snapped"])
    print(
        f"{len(records)} cameras, {len(roads)} roads, "
        f"{snapped} snapped, {time.time() - started:.1f}s",
        file=sys.stderr,
    )

    if args.database_url:
        print(f"upserted {write_postgres(records, args.database_url)} cameras")
        return 0

    if args.out:
        with open(args.out, "w") as f:
            write_geojson(records, f)
        print(f"wrote {len(records)} cameras to {args.out}")
    else:
        write_geojson(records, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
