"""Snap a camera to its nearest road and build its dead zone polygon.

This mirrors what the production ingestion job does in PostGIS
(ST_ClosestPoint / ST_LineSubstring / ST_Buffer) so the math can be
developed and tested from the command line before a roads table exists.

All geometry in and out is WGS84 lon/lat. Distance and buffering happen
in a metric projection, because buffering by a distance in feet is
meaningless in degrees. The projection is the UTM zone the camera falls
in, picked per camera: one zone covers 6 degrees of longitude, so a
region as wide as the east coast spans three of them.
"""

import math

from pyproj import Transformer
from shapely.geometry import LineString, Point, box
from shapely.ops import substring, transform
from shapely.strtree import STRtree

METERS_PER_FOOT = 0.3048

DEAD_ZONE_FT = 75.0
ROAD_WIDTH_FT = 24.0  # two 12ft lanes; the buffer is half this on each side
MAX_SNAP_FT = 150.0  # beyond this the camera is not watching that road

# Facing within this many degrees of perpendicular to the road tells us
# nothing about which way along the road the camera looks, so we treat it
# as unknown rather than guessing.
PERPENDICULAR_TOLERANCE_DEG = 15.0

_TRANSFORMERS = {}


def projection(lon):
    """Return (to_meters, to_degrees) for the UTM zone containing lon.

    Cached, because building a Transformer is far slower than using one and
    a regional run reuses the same two or three zones tens of thousands of
    times.
    """
    zone = int((lon + 180) // 6) + 1
    if zone not in _TRANSFORMERS:
        utm = f"EPSG:{32600 + zone}"
        _TRANSFORMERS[zone] = (
            Transformer.from_crs("EPSG:4326", utm, always_xy=True).transform,
            Transformer.from_crs(utm, "EPSG:4326", always_xy=True).transform,
        )
    return _TRANSFORMERS[zone]


class RoadIndex:
    """Bounding-box index over roads in WGS84.

    A multi-state region pulls in hundreds of thousands of road ways, and
    checking every camera against every road would not finish. The index
    narrows each camera to a handful of candidates; the exact distance is
    then measured in meters on those few.
    """

    # Degrees of padding around a camera when collecting candidates. A
    # degree of longitude is shorter than a degree of latitude, so this is
    # deliberately loose: it only has to avoid missing a road, not be tight.
    PAD_DEG = MAX_SNAP_FT * METERS_PER_FOOT / 111_320 * 2

    def __init__(self, roads):
        self.roads = list(roads)
        self.tree = STRtree(self.roads) if self.roads else None

    def candidates(self, lon, lat):
        if self.tree is None:
            return []
        pad = self.PAD_DEG
        found = self.tree.query(box(lon - pad, lat - pad, lon + pad, lat + pad))
        return [self.roads[i] for i in found]


def compute_dead_zone(lon, lat, facing_deg, roads):
    """Return the dead zone polygon (WGS84) for one camera."""
    return dead_zone_and_snap(lon, lat, facing_deg, roads)[0]


def dead_zone_and_snap(lon, lat, facing_deg, roads):
    """Return (dead zone polygon in WGS84, snapped to a road?).

    roads is a list of shapely LineStrings in WGS84, or a RoadIndex. If no
    road is close enough the dead zone is a plain circle around the camera,
    which is the conservative shape but worth counting separately: a lot of
    them means the road data is too thin, not that the cameras are rural.
    """
    index = roads if isinstance(roads, RoadIndex) else RoadIndex(roads)
    to_meters, to_degrees = projection(lon)

    camera = transform(to_meters, Point(lon, lat))
    nearby = [transform(to_meters, r) for r in index.candidates(lon, lat)]
    road = nearest_road(nearby, camera)

    if road is None:
        circle = camera.buffer(DEAD_ZONE_FT * METERS_PER_FOOT)
        return transform(to_degrees, circle), False

    return transform(to_degrees, road_dead_zone(road, camera, facing_deg)), True


def nearest_road(roads_m, camera_m):
    """Closest road within MAX_SNAP_FT, or None."""
    limit = MAX_SNAP_FT * METERS_PER_FOOT
    candidates = [r for r in roads_m if r.distance(camera_m) <= limit]
    if not candidates:
        return None
    return min(candidates, key=lambda r: r.distance(camera_m))


def road_dead_zone(road_m, camera_m, facing_deg):
    """Clip the watched stretch of road and buffer it to road width."""
    offset = road_m.project(camera_m)
    reach = DEAD_ZONE_FT * METERS_PER_FOOT
    forward = facing_along_road(road_m, offset, facing_deg)

    if forward is True:
        start, end = offset, offset + reach
    elif forward is False:
        start, end = offset - reach, offset
    else:
        start, end = offset - reach, offset + reach

    # substring clamps to the ends of the line, so a camera near the end of
    # a road segment just gets a shorter dead zone.
    clipped = substring(road_m, max(start, 0.0), min(end, road_m.length))
    return clipped.buffer(ROAD_WIDTH_FT / 2 * METERS_PER_FOOT, cap_style="flat")


def facing_along_road(road_m, offset, facing_deg):
    """True if the camera looks along the road's direction of travel, False if
    against it, None if unknown or too close to perpendicular to tell."""
    if facing_deg is None:
        return None

    delta = angle_between(facing_deg, road_bearing(road_m, offset))
    if abs(90 - delta) < PERPENDICULAR_TOLERANCE_DEG:
        return None
    return delta < 90


def road_bearing(road_m, offset):
    """Compass bearing of the road at the given distance along it."""
    step = 1.0
    a = road_m.interpolate(max(offset - step, 0.0))
    b = road_m.interpolate(min(offset + step, road_m.length))
    # UTM northing is y and easting is x, so bearing is measured from +y
    # clockwise, which is the reverse of the usual atan2 argument order.
    return math.degrees(math.atan2(b.x - a.x, b.y - a.y)) % 360


def angle_between(a, b):
    """Smallest angle between two bearings, 0-180."""
    return abs((a - b + 180) % 360 - 180)


def load_roads(path):
    """Read roads from a GeoJSON FeatureCollection of LineStrings."""
    import json

    with open(path) as f:
        data = json.load(f)
    return [
        LineString(feature["geometry"]["coordinates"])
        for feature in data["features"]
        if feature["geometry"]["type"] == "LineString"
    ]
