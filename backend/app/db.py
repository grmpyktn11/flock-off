"""The cameras table.

Only two questions get asked of it: which cameras are near this trip, and
which of them can see this route. Both are answered in SQL, because the
dead zone is a polygon and PostGIS is what knows how to intersect it.

Connections are opened per request. The spec puts pooling at the 1k-10k
user stage, and Supabase's own pooler already sits in front of this, so
there is nothing to pool yet.
"""

import json

import psycopg

from app.config import DATABASE_URL

# Cameras whose point falls in the trip's bounding box. The && operator is
# the one the GIST index answers.
_IN_BBOX = """
    SELECT id, osm_id, type, ST_Y(geom), ST_X(geom), facing_deg,
           operator, brand, road_name, road_ref,
           crime_count, crime_desc, arrest_count, arrest_desc,
           tract_income, county_income, usefulness_score, score_desc
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
      AND NOT ST_IsEmpty(dead_zone)
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


# The polygons handed to Valhalla as exclude_polygons. Expanding them is
# how a verification retry asks for a wider berth; ST_Buffer on geography
# takes metres, which is what the retry step counts in.
_DEAD_ZONES = """
    SELECT ST_AsGeoJSON(
               CASE WHEN %s > 0
                    THEN ST_Buffer(dead_zone::geography, %s)::geometry
                    ELSE dead_zone
               END)
    FROM cameras
    WHERE id = ANY(%s)
      AND dead_zone IS NOT NULL
      AND NOT ST_IsEmpty(dead_zone)
"""


def fetch_dead_zone_rings(
    camera_ids: list[int], expand_m: float = 0.0
) -> list[list[list[float]]]:
    """Outer rings as [[lng, lat], ...], the shape Valhalla wants."""
    if not camera_ids:
        return []
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(_DEAD_ZONES, (expand_m, expand_m, camera_ids))
            return [json.loads(row[0])["coordinates"][0] for row in cur.fetchall()]


# The facts the explanation feature grounds on, plus any explanation a
# previous request already paid for. One round trip for the whole batch.
_CAMERAS_FOR_EXPLAIN = """
    SELECT id, type, facing_deg, operator, brand, road_name, road_ref,
           road_class, maxspeed, crime_count, crime_desc,
           tract_income, county_income, arrest_count, arrest_desc,
           usefulness_score, score_desc, explanation
    FROM cameras
    WHERE id = ANY(%s)
      AND active
"""

_SAVE_EXPLANATION = """
    UPDATE cameras SET explanation = %s, explained_at = now() WHERE id = %s
"""


def fetch_cameras_for_explain(camera_ids: list[int]) -> list[tuple]:
    if not camera_ids:
        return []
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(_CAMERAS_FOR_EXPLAIN, (camera_ids,))
            return cur.fetchall()


def save_explanation(camera_id: int, text: str) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(_SAVE_EXPLANATION, (text, camera_id))


def route_wkt(route: list[tuple[float, float]]) -> str:
    """WKT LINESTRING from (lat, lng) points. WKT is x y, so lng first."""
    points = ", ".join(f"{lng} {lat}" for lat, lng in route)
    return f"LINESTRING({points})"
