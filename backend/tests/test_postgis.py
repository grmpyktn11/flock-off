"""The real PostGIS camera source.

Skipped unless DATABASE_URL is set, so the suite still runs on a checkout
with no infrastructure. These are the tests the mock cannot stand in for:
they check that the SQL is right, not that the pipeline is.
"""

import psycopg
import pytest

from app import cameras as camera_source
from app import config, db

pytestmark = pytest.mark.skipif(
    not config.DATABASE_URL, reason="needs DATABASE_URL"
)

# Fairfax Boulevard, the corridor used for the deep link premise test.
ORIGIN = (38.853999, -77.318748)
DESTINATION = (38.864420, -77.277596)


@pytest.fixture(autouse=True)
def use_real_cameras(monkeypatch):
    """Undo the suite-wide pin back to the mock source."""
    monkeypatch.setattr(config, "USE_MOCK_CAMERAS", False)


def a_dead_zone_centroid() -> tuple[float, float]:
    with psycopg.connect(config.DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ST_Y(ST_Centroid(dead_zone)), ST_X(ST_Centroid(dead_zone))"
                " FROM cameras WHERE dead_zone IS NOT NULL ORDER BY id LIMIT 1"
            )
            return cur.fetchone()


def test_bbox_returns_cameras_along_a_real_corridor():
    cameras = camera_source.in_bbox(ORIGIN, DESTINATION)
    assert len(cameras) > 10
    assert all(c.type in ("alpr", "speed_camera") for c in cameras)
    assert all(-78 < c.lng < -76 and 38 < c.lat < 40 for c in cameras)


def test_a_route_through_a_dead_zone_is_seen():
    lat, lng = a_dead_zone_centroid()
    cameras = camera_source.in_bbox((lat - 0.01, lng - 0.01), (lat + 0.01, lng + 0.01))
    assert cameras, "expected cameras around a known dead zone"

    # A short line straight through the middle of the polygon.
    through = [(lat, lng - 0.0008), (lat, lng + 0.0008)]
    assert camera_source.seen_by(through, cameras)


def test_a_route_nowhere_near_is_not_seen():
    cameras = camera_source.in_bbox(ORIGIN, DESTINATION)
    # Out in the Atlantic, well clear of any Virginia camera.
    at_sea = [(36.0, -70.0), (36.1, -69.9)]
    assert camera_source.seen_by(at_sea, cameras) == set()


def test_route_wkt_puts_longitude_first():
    """WKT is x y. Getting this backwards silently returns no matches."""
    assert db.route_wkt([(38.5, -77.5), (38.6, -77.4)]) == (
        "LINESTRING(-77.5 38.5, -77.4 38.6)"
    )
