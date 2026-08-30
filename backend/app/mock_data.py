"""Stand-in data sources.

Everything here replaces something that will be real later: the PostGIS
cameras table, Valhalla, Google Directions and Google Places. The shapes
of the return values match what those services will give us, so only this
module has to change when they are wired up.

Sample area is Fairfax / Herndon, Virginia.
"""

import math

from app.geo import EARTH_RADIUS_M, haversine_m, point_to_polyline_m, resample
from app.models import Camera

# A route is treated as seen by a camera if it passes within this many
# meters of it. The real check is ST_DWithin against the stored dead zone.
DEAD_ZONE_RADIUS_M = 23.0

# How far sideways the mock router swings to clear a camera, and how far
# ahead of the camera it starts the swing.
DETOUR_OFFSET_M = 250.0
DETOUR_REACH_M = 600.0

AVERAGE_SPEED_MPS = 13.4  # roughly 30 mph on suburban arterials


# Sample rows from the cameras table. The operator/brand/road context is
# what both the camera list and the explanation feature ground on, so the
# mock rows carry it the way real ingested rows do.
CAMERAS: list[Camera] = [
    # Spaced along the Herndon-to-Fairfax corridor, plus one sitting on top
    # of a common origin (unavoidable) and one off to the side (ignored).
    Camera(1, 1001001, "alpr", 38.95109, -77.37414, 90.0,
           operator="Fairfax County Police Department", brand="Flock Safety",
           road_name="Herndon Parkway"),
    Camera(2, 1001002, "alpr", 38.93258, -77.36219, None,
           operator="Fairfax County Police Department", brand="Flock Safety",
           road_name="Fairfax County Parkway", road_ref="VA 286"),
    Camera(3, 1001003, "speed_camera", 38.91407, -77.35024, 270.0,
           operator="Fairfax County Police Department",
           road_name="Leesburg Pike", road_ref="VA 7"),
    Camera(4, 1001004, "alpr", 38.89556, -77.33828, 180.0,
           operator="Town of Vienna Police Department", brand="Flock Safety",
           road_name="Chain Bridge Road", road_ref="VA 123"),
    Camera(5, 1001005, "alpr", 38.87705, -77.32633, None,
           brand="Flock Safety", road_name="Lee Highway", road_ref="US 29"),
    Camera(6, 1001006, "speed_camera", 38.85854, -77.31437, 0.0,
           operator="City of Fairfax Police Department",
           road_name="Main Street", road_ref="VA 236"),
    Camera(7, 1001007, "alpr", 38.96950, -77.38600, 45.0,
           operator="Town of Herndon Police Department", brand="Flock Safety",
           road_name="Elden Street"),
    Camera(8, 1001008, "alpr", 38.94300, -77.42000, None,
           brand="Flock Safety"),
]

# Sample rows behind the Places Autocomplete proxy.
PLACES: list[dict] = [
    {"place_id": "p_herndon_metro", "name": "Herndon Metro Station",
     "address": "585 Herndon Pkwy, Herndon, VA", "lat": 38.9470, "lng": -77.3930},
    {"place_id": "p_reston_town_center", "name": "Reston Town Center",
     "address": "11900 Market St, Reston, VA", "lat": 38.9586, "lng": -77.3570},
    {"place_id": "p_fairfax_corner", "name": "Fairfax Corner",
     "address": "11900 Palace Way, Fairfax, VA", "lat": 38.8611, "lng": -77.3760},
    {"place_id": "p_fair_oaks_mall", "name": "Fair Oaks Mall",
     "address": "11750 Fair Oaks Mall, Fairfax, VA", "lat": 38.8688, "lng": -77.3592},
    {"place_id": "p_dulles_airport", "name": "Washington Dulles International Airport",
     "address": "1 Saarinen Cir, Dulles, VA", "lat": 38.9531, "lng": -77.4565},
    {"place_id": "p_vienna_metro", "name": "Vienna Metro Station",
     "address": "9550 Saintsbury Dr, Fairfax, VA", "lat": 38.8776, "lng": -77.2723},
    # These two bracket the sample camera corridor above. Without a pair
    # that actually crosses the cameras, a demo driven from the search
    # screen plans a trip with nothing to avoid and looks broken.
    {"place_id": "p_floris", "name": "Floris",
     "address": "Floris, Herndon, VA", "lat": 38.9696, "lng": -77.3861},
    {"place_id": "p_burke_centre", "name": "Burke Centre",
     "address": "Burke Centre, Burke, VA", "lat": 38.8462, "lng": -77.3064},
]


def camera_explanations(camera_ids: list[int]) -> dict[int, str]:
    """Stand-in for the Claude-written placement explanations.

    Deterministic sentences assembled from the same fields the real prompt
    grounds on, so the offline demo reads like the real feature. Unknown
    ids are left out of the result, matching how the real path treats a
    camera that is not in the table.
    """
    by_id = {c.id: c for c in CAMERAS}
    return {
        camera_id: _canned_explanation(by_id[camera_id])
        for camera_id in camera_ids
        if camera_id in by_id
    }


def _canned_explanation(camera: Camera) -> str:
    where = f"on {camera.road_name}" if camera.road_name else "here"
    if camera.type == "speed_camera":
        return (
            "This speed camera cannot be evaluated from public data - no "
            "local crash figures are published."
        )
    return (
        "This plate reader cannot be evaluated from public data; audits "
        "found most Flock scans are never linked to any investigation."
    )


def search_places(query: str, lat: float | None, lng: float | None) -> list[dict]:
    """Stand-in for Google Places Autocomplete."""
    query = query.strip().lower()
    matches = [
        p for p in PLACES
        if query in p["name"].lower() or query in p["address"].lower()
    ]
    if lat is not None and lng is not None:
        matches.sort(key=lambda p: haversine_m((lat, lng), (p["lat"], p["lng"])))
    return matches


def cameras_in_bbox(
    origin: tuple[float, float], destination: tuple[float, float], padding_m: float = 3000.0
) -> list[Camera]:
    """Stand-in for the PostGIS bounding box query around a trip."""
    pad_lat = padding_m / 111320.0
    mid_lat = (origin[0] + destination[0]) / 2
    pad_lng = padding_m / (111320.0 * math.cos(math.radians(mid_lat)))
    min_lat = min(origin[0], destination[0]) - pad_lat
    max_lat = max(origin[0], destination[0]) + pad_lat
    min_lng = min(origin[1], destination[1]) - pad_lng
    max_lng = max(origin[1], destination[1]) + pad_lng
    return [
        c for c in CAMERAS
        if min_lat <= c.lat <= max_lat and min_lng <= c.lng <= max_lng
    ]


def google_directions(
    origin: tuple[float, float],
    waypoints: list[tuple[float, float]],
    destination: tuple[float, float],
) -> tuple[list[tuple[float, float]], int]:
    """Stand-in for the Routes API: straight legs, and how long they take."""
    points = [origin, *waypoints, destination]
    route: list[tuple[float, float]] = []
    for i in range(len(points) - 1):
        leg = resample([points[i], points[i + 1]], 100.0)
        route.extend(leg if not route else leg[1:])
    return route, _eta_seconds(route)


def google_route_eta(
    origin: tuple[float, float],
    waypoints: list[tuple[float, float]],
    destination: tuple[float, float],
) -> int:
    """Stand-in for the Routes API duration, waypoints included."""
    return google_directions(origin, waypoints, destination)[1]


def google_baseline_route(
    origin: tuple[float, float], destination: tuple[float, float]
) -> tuple[list[tuple[float, float]], int]:
    """Stand-in for Google's default route: the direct path, no avoidance."""
    return google_directions(origin, [], destination)


def valhalla_route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    cameras: list[Camera],
    expand_m: float = 0.0,
) -> tuple[list[tuple[float, float]], int]:
    """Stand-in for Valhalla with exclude_polygons set to the dead zones.

    The real engine reroutes onto parallel streets. Here we bow the direct
    path sideways around each camera, which produces the same thing the
    waypoint picker cares about: spans where our route leaves the baseline.
    expand_m stands in for widening the exclusion polygons on a retry.
    """
    route = resample([origin, destination], 100.0)
    side_lat, side_lng = _perpendicular(origin, destination)
    detoured = [
        _offset_point(p, side_lat, side_lng, _detour_offset_m(p, cameras, expand_m))
        for p in route
    ]
    detoured[0] = origin
    detoured[-1] = destination
    return detoured, _eta_seconds(detoured)


def _detour_offset_m(
    point: tuple[float, float], cameras: list[Camera], expand_m: float
) -> float:
    """How far sideways this point has to move to clear the nearby cameras."""
    offsets = [
        (DETOUR_OFFSET_M + expand_m) * (1 - haversine_m(point, (c.lat, c.lng)) / DETOUR_REACH_M)
        for c in cameras
        if haversine_m(point, (c.lat, c.lng)) < DETOUR_REACH_M
    ]
    return max(offsets, default=0.0)


def _perpendicular(
    origin: tuple[float, float], destination: tuple[float, float]
) -> tuple[float, float]:
    """Unit vector, in degrees, at right angles to the origin-destination line."""
    d_lat = destination[0] - origin[0]
    d_lng = destination[1] - origin[1]
    length = math.hypot(d_lat, d_lng)
    if length == 0:
        return 0.0, 0.0
    return -d_lng / length, d_lat / length


def _offset_point(
    point: tuple[float, float], side_lat: float, side_lng: float, meters: float
) -> tuple[float, float]:
    if meters == 0:
        return point
    return (
        point[0] + side_lat * _m_to_deg_lat(meters),
        point[1] + side_lng * _m_to_deg_lng(meters, point[0]),
    )


def _m_to_deg_lat(meters: float) -> float:
    return meters / (math.pi / 180 * EARTH_RADIUS_M)


def _m_to_deg_lng(meters: float, lat: float) -> float:
    return meters / (math.pi / 180 * EARTH_RADIUS_M * math.cos(math.radians(lat)))


def _eta_seconds(route: list[tuple[float, float]]) -> int:
    length = sum(haversine_m(route[i], route[i + 1]) for i in range(len(route) - 1))
    return round(length / AVERAGE_SPEED_MPS)


def ids_seeing_route(
    cameras: list[Camera], route: list[tuple[float, float]]
) -> set[int]:
    """Stand-in for ST_Intersects against the stored dead zone.

    A circle around the camera point, so it is directionally blind: it
    flags cameras facing away from the driver that the real dead zone
    would not. Counts from this are pessimistic on purpose.
    """
    return {
        c.id
        for c in cameras
        if point_to_polyline_m((c.lat, c.lng), route) <= DEAD_ZONE_RADIUS_M
    }
