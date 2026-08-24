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
    first_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    active      BOOLEAN NOT NULL DEFAULT TRUE
);

-- /plan pulls cameras by trip bounding box and checks routes against dead
-- zones, so both geometry columns need their own index.
CREATE INDEX IF NOT EXISTS cameras_geom_idx      ON cameras USING GIST (geom);
CREATE INDEX IF NOT EXISTS cameras_dead_zone_idx ON cameras USING GIST (dead_zone);
CREATE INDEX IF NOT EXISTS cameras_active_idx    ON cameras (active);

-- Daily ingestion upsert. A camera already in the table keeps its first_seen
-- and just gets its last_seen bumped; anything not touched by today's run is
-- swept to active = FALSE separately (see ingest.py).
-- Params: osm_id, type, lon, lat, facing_deg, dead_zone WKT
--
-- INSERT INTO cameras (osm_id, type, geom, facing_deg, dead_zone)
-- VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s,
--         ST_SetSRID(ST_GeomFromText(%s), 4326))
-- ON CONFLICT (osm_id) DO UPDATE SET
--     type       = EXCLUDED.type,
--     geom       = EXCLUDED.geom,
--     facing_deg = EXCLUDED.facing_deg,
--     dead_zone  = EXCLUDED.dead_zone,
--     last_seen  = now(),
--     active     = TRUE;

-- The ingestion job and the backend both connect as postgres over a direct
-- connection, which bypasses RLS. Nothing should reach this table through
-- Supabase's PostgREST layer using the anon key that ships inside the app
-- bundle, so enable RLS and add no policies: every anon and authenticated
-- request is denied. Supabase's linter reports this as an INFO notice
-- ("RLS enabled, no policies"), which is the intended state here.
ALTER TABLE cameras ENABLE ROW LEVEL SECURITY;
