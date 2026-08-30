"""Pull cameras, and the roads they watch, out of OpenStreetMap.

One query returns both: the camera nodes in a bounding box, plus every
road way within SNAP_RADIUS_M of one of them. That is a few thousand
ways for a town and a few hundred thousand for the east coast, which is
still far less than a roads table for the same area.

Large regions are split into tiles. The public Overpass instance will
refuse a single query covering several states, and it rate limits, so
tiles are fetched one at a time with backoff.
"""

import itertools
import time

import requests
from shapely.geometry import LineString

from ingestion import regions
from ingestion.deadzone import Road

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Overpass rejects requests from clients that do not identify themselves.
HEADERS = {"User-Agent": "flock-off/0.1 (camera-avoiding navigation)"}

# Named regions as (south, west, north, east), the order Overpass expects.
# Defined in regions.json at the repo root, which the Valhalla tile build
# reads too, so a new city is one edit in one place.
REGIONS = regions.REGIONS

# Roads this far from a camera or nearer are worth pulling. Kept a little
# tighter than the snapping limit in deadzone.py so we do not drag in the
# whole grid around every urban camera.
SNAP_RADIUS_M = 60

DRIVABLE = "^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|service|.*_link)$"

QUERY_TEMPLATE = """
[out:json][timeout:{timeout}];
(
  node["man_made"="surveillance"]["surveillance:type"="ALPR"]({bbox});
  node["highway"="speed_camera"]({bbox});
)->.cams;
way(around.cams:{radius})["highway"~"{drivable}"]->.roads;
(.cams; .roads;);
out body geom;
"""

# One tile of this size returns a few MB and finishes in seconds. Bigger
# tiles start hitting the public instance's memory ceiling.
TILE_DEG = 2.0

# The public instance allows a couple of queries in flight per IP. A pause
# between tiles keeps a long regional run from being throttled to a crawl.
TILE_PAUSE_S = 3
BACKOFF_S = 45
MAX_ATTEMPTS = 4


def build_query(bbox, timeout=600):
    return QUERY_TEMPLATE.format(
        bbox=",".join(str(v) for v in bbox),
        radius=SNAP_RADIUS_M,
        drivable=DRIVABLE,
        timeout=timeout,
    )


def tiles(bbox, size_deg=TILE_DEG):
    """Split a bounding box into tiles of at most size_deg on a side."""
    south, west, north, east = bbox
    lats = frange(south, north, size_deg)
    lons = frange(west, east, size_deg)
    for lat, lon in itertools.product(lats, lons):
        yield (lat, lon, min(lat + size_deg, north), min(lon + size_deg, east))


def frange(start, stop, step):
    values = []
    value = start
    while value < stop:
        values.append(value)
        value += step
    return values or [start]


def fetch(bbox, url=OVERPASS_URL, on_tile=None):
    """Return (cameras, roads) for a bounding box of any size.

    Cameras are dicts; roads are shapely LineStrings in WGS84. A camera
    seen in two overlapping tiles is returned once.
    """
    cameras = {}
    roads = {}
    tile_list = list(tiles(bbox))

    for i, tile in enumerate(tile_list):
        elements = fetch_tile(tile, url)
        for element in elements:
            if element["type"] == "node":
                cameras[element["id"]] = parse_node(element)
            elif element["type"] == "way" and len(element.get("geometry", [])) > 1:
                roads[element["id"]] = parse_way(element)
        if on_tile:
            on_tile(i + 1, len(tile_list), len(cameras), len(roads))
        if i + 1 < len(tile_list):
            time.sleep(TILE_PAUSE_S)

    return list(cameras.values()), list(roads.values())


def fetch_tile(bbox, url=OVERPASS_URL):
    """Fetch one tile, retrying when the public instance throttles us."""
    for attempt in range(MAX_ATTEMPTS):
        response = requests.post(
            url, data={"data": build_query(bbox)}, headers=HEADERS, timeout=900
        )
        if response.status_code in (429, 504):
            time.sleep(BACKOFF_S)
            continue
        response.raise_for_status()
        return response.json().get("elements", [])
    raise RuntimeError(f"Overpass kept throttling tile {bbox}")


def parse_way(way):
    tags = way.get("tags", {})
    return Road(
        geom=LineString([(p["lon"], p["lat"]) for p in way["geometry"]]),
        name=tags.get("name"),
        ref=tags.get("ref"),
        road_class=tags.get("highway"),
        maxspeed=tags.get("maxspeed"),
    )


def parse_node(node):
    tags = node.get("tags", {})
    return {
        "osm_id": node["id"],
        "type": camera_type(tags),
        "lon": node["lon"],
        "lat": node["lat"],
        "facing_deg": parse_direction(tags),
        # Who runs the camera and whose product it is, when OSM knows.
        # This is the difference between "a camera" and "a Flock Safety
        # reader operated by Fairfax County Police", which is the version
        # worth telling a driver.
        "operator": tags.get("operator"),
        "brand": tags.get("brand") or tags.get("manufacturer"),
    }


def camera_type(tags):
    if tags.get("highway") == "speed_camera":
        return "speed_camera"
    return "alpr"


def parse_direction(tags):
    """Compass bearing the camera faces, or None if not tagged or not numeric.

    camera:direction is the current tag; direction is the legacy one and is
    also used for non-numeric values like "forward" or "N", which we cannot
    turn into a bearing without knowing the road, so those are treated as
    unknown.
    """
    for key in ("camera:direction", "direction"):
        raw = tags.get(key)
        if raw is None:
            continue
        try:
            return float(raw) % 360
        except ValueError:
            continue
    return None
