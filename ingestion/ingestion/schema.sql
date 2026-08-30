-- Cameras table for the camera-avoiding navigation backend.
-- Requires PostGIS: CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS cameras (
    id          BIGSERIAL PRIMARY KEY,
    osm_id      BIGINT NOT NULL UNIQUE,
    type        TEXT NOT NULL CHECK (type IN ('alpr', 'speed_camera')),
    geom        GEOMETRY(Point, 4326) NOT NULL,
    facing_deg  DOUBLE PRECISION CHECK (facing_deg >= 0 AND facing_deg < 360),
    dead_zone   GEOMETRY(Polygon, 4326),
    -- Context from OSM, for telling the driver what this thing is rather
    -- than just where. operator/brand come off the camera node; the road
    -- name and ref come from the way the camera was snapped to.
    operator    TEXT,
    brand       TEXT,
    road_name   TEXT,
    road_ref    TEXT,
    -- The road's OSM highway= class and posted maxspeed, from the same
    -- snapped way. maxspeed stays text because OSM values are strings:
    -- "45 mph", "50", "none".
    road_class  TEXT,
    maxspeed    TEXT,
    -- The AI-written "why is a camera here" paragraph, generated once on
    -- first request and served from this row after. explained_at says when,
    -- so a stale one can be found and regenerated. The ingestion upsert
    -- never touches either, so a nightly run keeps the cache.
    explanation  TEXT,
    explained_at TIMESTAMPTZ,
    -- Ground truth from public records, filled by ingestion/enrich.py:
    -- reported crime near the camera (crime_desc says what was counted and
    -- from which source, since jurisdictions publish differently) and the
    -- neighborhood's median household income against its county's, from
    -- the Census ACS. These are what let an explanation say whether the
    -- placement matches the local crime picture instead of guessing.
    crime_count   INTEGER,
    crime_desc    TEXT,
    tract_income  INTEGER,
    county_income INTEGER,
    -- Arrests recorded in the camera's police service area (area-level,
    -- never "arrests produced by this camera" - nobody publishes that),
    -- and the deterministic usefulness score computed from all factors.
    -- score_desc names the factors used, e.g. "scored on 2 of 3".
    arrest_count     INTEGER,
    arrest_desc      TEXT,
    usefulness_score INTEGER,
    score_desc       TEXT,
    enriched_at   TIMESTAMPTZ,
    first_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    active      BOOLEAN NOT NULL DEFAULT TRUE
);

-- Databases created before these columns existed pick them up here.
-- Re-running this file with psql -f is how schema changes are applied,
-- so everything in it has to be safe to run twice.
ALTER TABLE cameras
    ADD COLUMN IF NOT EXISTS road_class    TEXT,
    ADD COLUMN IF NOT EXISTS maxspeed      TEXT,
    ADD COLUMN IF NOT EXISTS explanation   TEXT,
    ADD COLUMN IF NOT EXISTS explained_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS crime_count   INTEGER,
    ADD COLUMN IF NOT EXISTS crime_desc    TEXT,
    ADD COLUMN IF NOT EXISTS tract_income  INTEGER,
    ADD COLUMN IF NOT EXISTS county_income INTEGER,
    ADD COLUMN IF NOT EXISTS arrest_count     INTEGER,
    ADD COLUMN IF NOT EXISTS arrest_desc      TEXT,
    ADD COLUMN IF NOT EXISTS usefulness_score INTEGER,
    ADD COLUMN IF NOT EXISTS score_desc       TEXT,
    ADD COLUMN IF NOT EXISTS enriched_at   TIMESTAMPTZ;

-- /plan pulls cameras by trip bounding box and checks routes against dead
-- zones, so both geometry columns need their own index.
CREATE INDEX IF NOT EXISTS cameras_geom_idx      ON cameras USING GIST (geom);
CREATE INDEX IF NOT EXISTS cameras_dead_zone_idx ON cameras USING GIST (dead_zone);
CREATE INDEX IF NOT EXISTS cameras_active_idx    ON cameras (active);

-- Daily ingestion upsert. A camera already in the table keeps its first_seen
-- and just gets its last_seen bumped; anything not touched by today's run is
-- swept to active = FALSE separately (see ingest.py).
-- Params: osm_id, type, lon, lat, facing_deg, dead_zone WKT, operator,
-- brand, road_name, road_ref, road_class, maxspeed. The real statement is
-- UPSERT_SQL in ingest.py; the point to keep in view here is what it does
-- NOT set: explanation and explained_at survive every re-ingest.
--
-- INSERT INTO cameras (osm_id, type, geom, facing_deg, dead_zone,
--                      operator, brand, road_name, road_ref,
--                      road_class, maxspeed)
-- VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s,
--         ST_SetSRID(ST_GeomFromText(%s), 4326), %s, %s, %s, %s, %s, %s)
-- ON CONFLICT (osm_id) DO UPDATE SET
--     type       = EXCLUDED.type,
--     geom       = EXCLUDED.geom,
--     facing_deg = EXCLUDED.facing_deg,
--     dead_zone  = EXCLUDED.dead_zone,
--     operator   = EXCLUDED.operator,
--     brand      = EXCLUDED.brand,
--     road_name  = EXCLUDED.road_name,
--     road_ref   = EXCLUDED.road_ref,
--     road_class = EXCLUDED.road_class,
--     maxspeed   = EXCLUDED.maxspeed,
--     last_seen  = now(),
--     active     = TRUE;

-- The ingestion job and the backend both connect as postgres over a direct
-- connection, which bypasses RLS. Nothing should reach this table through
-- Supabase's PostgREST layer using the anon key that ships inside the app
-- bundle, so enable RLS and add no policies: every anon and authenticated
-- request is denied. Supabase's linter reports this as an INFO notice
-- ("RLS enabled, no policies"), which is the intended state here.
ALTER TABLE cameras ENABLE ROW LEVEL SECURITY;
