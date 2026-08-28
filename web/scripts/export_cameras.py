"""Export the DMV cameras to static GeoJSON for the showcase site.

Reads the same DATABASE_URL as the backend (repo root .env) and writes
web/public/data/cameras.geojson: one FeatureCollection holding a Point
per camera plus its dead-zone Polygon, matched up by camera id. The site
is static, so this runs once locally and the output is committed.

    python web/scripts/export_cameras.py
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

import psycopg  # noqa: E402

from app.config import DATABASE_URL  # noqa: E402  (loads the root .env)

OUT = REPO / "web" / "public" / "data" / "cameras.geojson"

# The DB holds every region ever ingested; the site shows the serving
# area. Same bbox source as everything else: regions.json, in Overpass
# [south, west, north, east] order.
REGION = "dmv"

_EXPORT = """
    SELECT id, type, ST_X(geom), ST_Y(geom), facing_deg, operator, brand,
           road_name, road_ref, explanation, ST_AsGeoJSON(dead_zone)
    FROM cameras
    WHERE active
      AND geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
    ORDER BY id
"""


def main() -> None:
    if not DATABASE_URL:
        sys.exit("DATABASE_URL is not set; put it in the repo root .env")

    regions = json.loads((REPO / "regions.json").read_text())
    south, west, north, east = regions[REGION]["bbox"]

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(_EXPORT, (west, south, east, north))
            rows = cur.fetchall()

    features = []
    for (
        camera_id, kind, lng, lat, facing_deg, operator, brand,
        road_name, road_ref, explanation, dead_zone,
    ) in rows:
        properties = {
            "id": camera_id,
            "kind": "camera",
            "type": kind,
            "facing_deg": facing_deg,
            "operator": operator,
            "brand": brand,
            "road_name": road_name,
            "road_ref": road_ref,
            "explanation": explanation,
        }
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(lng, 6), round(lat, 6)],
            },
            "properties": {k: v for k, v in properties.items() if v is not None},
        })
        if dead_zone:
            features.append({
                "type": "Feature",
                "geometry": json.loads(dead_zone),
                "properties": {"id": camera_id, "kind": "dead_zone", "type": kind},
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"type": "FeatureCollection", "features": features},
        separators=(",", ":"),
    ))

    cameras = sum(1 for f in features if f["properties"]["kind"] == "camera")
    explained = sum(
        1 for f in features
        if f["properties"]["kind"] == "camera" and "explanation" in f["properties"]
    )
    print(f"{cameras} cameras ({explained} with explanations), "
          f"{len(features) - cameras} dead zones -> {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
