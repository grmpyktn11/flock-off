"""Run with: python -m pytest tests -q"""

from shapely.geometry import LineString, Point

from ingestion import overpass
from shapely.ops import transform

from ingestion.deadzone import (
    DEAD_ZONE_FT,
    METERS_PER_FOOT,
    compute_dead_zone,
    projection,
    road_bearing,
)


def to_meters(geom):
    return transform(projection(geom.centroid.x)[0], geom)

# A straight west-to-east road through Herndon, and a camera sitting on it.
ROAD = LineString([(-77.3900, 38.9700), (-77.3700, 38.9700)])
CAMERA = (-77.3800, 38.9700)


def length_along_road_m(polygon):
    """Rough length of a dead zone measured along the road it hugs."""
    minx, miny, maxx, maxy = to_meters(polygon).bounds
    return maxx - minx


def test_parse_direction_prefers_camera_direction():
    assert overpass.parse_direction({"camera:direction": "90", "direction": "270"}) == 90


def test_parse_direction_falls_back_to_legacy_tag():
    assert overpass.parse_direction({"direction": "270"}) == 270


def test_parse_direction_ignores_non_numeric_and_missing():
    assert overpass.parse_direction({"direction": "forward"}) is None
    assert overpass.parse_direction({}) is None


def test_camera_type():
    assert overpass.camera_type({"highway": "speed_camera"}) == "speed_camera"
    assert overpass.camera_type({"surveillance:type": "ALPR"}) == "alpr"


def test_road_bearing_is_compass_east():
    # Bearings are measured on the UTM grid, which is off true north by up to
    # ~2 degrees at this longitude. That is far inside the tolerance we use to
    # decide which way a camera looks, so we do not correct for it.
    road_m = to_meters(ROAD)
    assert abs(road_bearing(road_m, road_m.length / 2) - 90) < 2


def test_unknown_facing_covers_both_directions():
    zone = compute_dead_zone(*CAMERA, None, [ROAD])
    expected = 2 * DEAD_ZONE_FT * METERS_PER_FOOT
    assert abs(length_along_road_m(zone) - expected) < 1


def test_known_facing_covers_one_direction_only():
    zone = compute_dead_zone(*CAMERA, 90, [ROAD])
    expected = DEAD_ZONE_FT * METERS_PER_FOOT
    assert abs(length_along_road_m(zone) - expected) < 1


def test_facing_east_and_west_produce_opposite_halves():
    east = compute_dead_zone(*CAMERA, 90, [ROAD])
    west = compute_dead_zone(*CAMERA, 270, [ROAD])
    assert east.centroid.x > CAMERA[0] > west.centroid.x


def test_perpendicular_facing_is_treated_as_unknown():
    # A camera aimed across the road tells us nothing about which way it
    # watches, so it should behave like an untagged one.
    zone = compute_dead_zone(*CAMERA, 0, [ROAD])
    expected = 2 * DEAD_ZONE_FT * METERS_PER_FOOT
    assert abs(length_along_road_m(zone) - expected) < 1


def test_camera_far_from_any_road_gets_a_plain_circle():
    far = (-77.2000, 38.8000)
    zone = compute_dead_zone(*far, 90, [ROAD])
    assert zone.contains(Point(far))
    radius = DEAD_ZONE_FT * METERS_PER_FOOT
    assert abs(length_along_road_m(zone) - 2 * radius) < 1


def test_nearest_road_wins():
    near = LineString([(-77.3900, 38.9701), (-77.3700, 38.9701)])
    far = LineString([(-77.3900, 38.9704), (-77.3700, 38.9704)])
    zone = compute_dead_zone(*CAMERA, None, [far, near])
    assert zone.centroid.y < 38.97025


def test_dead_zone_contains_the_camera():
    for facing in (None, 90, 270, 0):
        assert compute_dead_zone(*CAMERA, facing, [ROAD]).buffer(1e-7).contains(
            Point(CAMERA)
        )


# Wide-area pieces


def test_tiles_cover_a_small_box_in_one_piece():
    assert list(overpass.tiles((38.0, -78.0, 39.0, -77.0), size_deg=2.0)) == [
        (38.0, -78.0, 39.0, -77.0)
    ]


def test_tiles_split_a_large_box_and_stay_inside_it():
    bbox = (24.5, -83.5, 47.5, -66.9)
    tiles = list(overpass.tiles(bbox, size_deg=2.0))
    assert len(tiles) == 12 * 9
    south, west, north, east = bbox
    for s, w, n, e in tiles:
        assert south <= s < n <= north
        assert west <= w < e <= east


def test_parse_way_becomes_a_linestring():
    way = {"geometry": [{"lon": -77.39, "lat": 38.97}, {"lon": -77.37, "lat": 38.97}]}
    road = overpass.parse_way(way)
    assert list(road.geom.coords) == [(-77.39, 38.97), (-77.37, 38.97)]


def test_utm_zone_follows_longitude():
    from ingestion.deadzone import projection

    # The east coast spans three zones, so the projection cannot be fixed.
    assert projection(-83.0) is not projection(-77.0)
    assert projection(-77.0) is projection(-75.5)
    assert projection(-77.0) is not projection(-67.0)


def test_road_index_returns_only_nearby_candidates():
    from ingestion.deadzone import RoadIndex

    far = LineString([(-70.0, 38.97), (-70.1, 38.97)])
    index = RoadIndex([ROAD, far])
    # Bare LineStrings are wrapped in Road on the way in.
    assert [r.geom for r in index.candidates(*CAMERA)] == [ROAD]


def test_road_index_handles_no_roads():
    from ingestion.deadzone import RoadIndex

    assert RoadIndex([]).candidates(*CAMERA) == []


def test_dead_zone_and_snap_reports_which_road_was_found():
    from ingestion.deadzone import Road, dead_zone_and_snap

    named = Road(geom=ROAD, name="Elden Street", ref="VA-606")
    snapped = dead_zone_and_snap(*CAMERA, 90, [named])[1]
    assert snapped is not None
    assert snapped.name == "Elden Street"
    assert snapped.ref == "VA-606"
    assert dead_zone_and_snap(-77.2000, 38.8000, 90, [named])[1] is None


def test_camera_at_the_end_of_a_road_facing_off_it_still_gets_a_dead_zone():
    """The directional clip has nothing to clip here.

    Clamping start and end to the same point makes a zero-length line, and
    the flat buffer of that is an empty polygon. Six of the 2,872 real DMV
    cameras hit this. An empty dead zone intersects nothing, so the camera
    silently stops being checked, which is the one failure this whole
    table exists to prevent.
    """
    from shapely.geometry import LineString

    from ingestion.deadzone import compute_dead_zone

    # A camera on the last node of the road, facing further along it.
    road = LineString([(-77.30, 38.85), (-77.29, 38.85)])
    zone = compute_dead_zone(-77.29, 38.85, 90.0, [road])

    assert not zone.is_empty
    assert zone.area > 0


def test_every_region_is_usable():
    """regions.json is the one place a new city is added, so it is checked.

    A typo here is not a crash, it is a routing engine quietly built for
    the wrong patch of ground.
    """
    from ingestion import regions

    assert regions.names(), "no regions defined"
    for name in regions.names():
        south, west, north, east = regions.bbox(name)
        assert -90 <= south < north <= 90, f"{name}: bad latitudes"
        assert -180 <= west < east <= 180, f"{name}: bad longitudes"
        assert regions.description(name), f"{name}: say what it covers"


def test_osmium_bbox_reorders_the_corners():
    """Overpass wants south,west,north,east and osmium wants left,bottom,
    right,top. Feeding one order to the other clips the wrong ground."""
    from ingestion import regions

    south, west, north, east = regions.bbox("dmv")
    assert regions.osmium_bbox("dmv") == f"{west},{south},{east},{north}"


def test_overpass_regions_come_from_the_shared_file():
    """The tile build reads the same file, so they cannot drift apart."""
    from ingestion import overpass, regions

    assert overpass.REGIONS == regions.REGIONS


def test_a_region_with_extracts_lists_real_looking_downloads():
    from ingestion import regions

    for url in regions.osm_extracts("dmv"):
        assert url.startswith("https://download.geofabrik.de/")
        assert url.endswith(".osm.pbf")
