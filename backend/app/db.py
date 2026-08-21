"""The cameras table.

Only two questions get asked of it: which cameras are near this trip, and
which of them can see this route. Both are answered in SQL, because the
dead zone is a polygon and PostGIS is what knows how to intersect it.

Connections are opened per request. The spec puts pooling at the 1k-10k
user stage, and Supabase's own pooler already sits in front of this, so
there is nothing to pool yet.
"""

import psycopg

from app.config import DATABASE_URL

# Cameras whose point falls in the trip's bounding box. The && operator is
# the one the GIST index answers.
_IN_BBOX = """
    SELECT id, osm_id, type, ST_Y(geom), ST_X(geom), facing_deg
    FROM cameras
    WHERE active
      AND geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
"""

# Which of these cameras actually watch the route. One round trip for the
# whole list rather than a query per camera.
_SEEING_ROUTE = """
    SELECT id
    FROM cameras
    WHERE id = ANY(%s)
      AND dead_zone IS NOT NULL
      AND ST_Intersects(dead_zone, ST_SetSRID(ST_GeomFromText(%s), 4326))
"""


def fetch_cameras_in_bbox(min_lng, min_lat, max_lng, max_lat) -> list[tuple]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(_IN_BBOX, (min_lng, min_lat, max_lng, max_lat))
            return cur.fetchall()


def fetch_ids_seeing_route(camera_ids: list[int], route_wkt: str) -> set[int]:
    if not camera_ids:
        return set()
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(_SEEING_ROUTE, (camera_ids, route_wkt))
            return {row[0] for row in cur.fetchall()}


def route_wkt(route: list[tuple[float, float]]) -> str:
    """WKT LINESTRING from (lat, lng) points. WKT is x y, so lng first."""
    points = ", ".join(f"{lng} {lat}" for lat, lng in route)
    return f"LINESTRING({points})"
