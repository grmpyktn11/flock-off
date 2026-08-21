"""Geometry helpers: polyline codec and distance math.

Everything here is plain math on (lat, lng) pairs so the backend can run
without PostGIS. Distances are in meters.
"""

import math

EARTH_RADIUS_M = 6371008.8


def decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """Decode an encoded polyline into (lat, lng) points.

    Google encodes at precision 5, Valhalla at 6. Decoding one as the
    other silently puts the route in the wrong hemisphere rather than
    raising, so the caller says which it has.
    """
    points = []
    index = 0
    lat = 0
    lng = 0
    scale = float(10**precision)
    while index < len(encoded):
        for is_lat in (True, False):
            result = 0
            shift = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else (result >> 1)
            if is_lat:
                lat += delta
            else:
                lng += delta
        points.append((lat / scale, lng / scale))
    return points


def encode_polyline(points: list[tuple[float, float]]) -> str:
    """Encode (lat, lng) points into a Google encoded polyline (precision 5)."""
    out = []
    prev_lat = 0
    prev_lng = 0
    for lat, lng in points:
        scaled_lat = round(lat * 1e5)
        scaled_lng = round(lng * 1e5)
        out.append(_encode_value(scaled_lat - prev_lat))
        out.append(_encode_value(scaled_lng - prev_lng))
        prev_lat = scaled_lat
        prev_lng = scaled_lng
    return "".join(out)


def _encode_value(value: int) -> str:
    value = ~(value << 1) if value < 0 else (value << 1)
    chunks = []
    while value >= 0x20:
        chunks.append(chr((0x20 | (value & 0x1F)) + 63))
        value >>= 5
    chunks.append(chr(value + 63))
    return "".join(chunks)


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two (lat, lng) points, in meters."""
    lat1, lng1 = math.radians(a[0]), math.radians(a[1])
    lat2, lng2 = math.radians(b[0]), math.radians(b[1])
    d_lat = lat2 - lat1
    d_lng = lng2 - lng1
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _to_meters(point: tuple[float, float], origin: tuple[float, float]) -> tuple[float, float]:
    """Project a point to local flat x/y meters relative to an origin.

    Trip-sized areas are small enough that a flat projection is accurate
    to well under the thresholds we compare against.
    """
    x = math.radians(point[1] - origin[1]) * EARTH_RADIUS_M * math.cos(math.radians(origin[0]))
    y = math.radians(point[0] - origin[0]) * EARTH_RADIUS_M
    return x, y


def point_to_segment_m(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    """Shortest distance from a point to a line segment, in meters."""
    px, py = _to_meters(point, start)
    ex, ey = _to_meters(end, start)
    seg_len_sq = ex * ex + ey * ey
    if seg_len_sq == 0:
        return math.hypot(px, py)
    t = max(0.0, min(1.0, (px * ex + py * ey) / seg_len_sq))
    return math.hypot(px - t * ex, py - t * ey)


def point_to_polyline_m(point: tuple[float, float], line: list[tuple[float, float]]) -> float:
    """Shortest distance from a point to a polyline, in meters."""
    if len(line) == 1:
        return haversine_m(point, line[0])
    return min(
        point_to_segment_m(point, line[i], line[i + 1]) for i in range(len(line) - 1)
    )


def resample(line: list[tuple[float, float]], interval_m: float) -> list[tuple[float, float]]:
    """Return points spaced roughly interval_m apart along the polyline.

    The first and last points are always kept so a span can reach either end.
    """
    if len(line) < 2:
        return list(line)
    samples = [line[0]]
    carry = 0.0
    for i in range(len(line) - 1):
        start = line[i]
        end = line[i + 1]
        seg_len = haversine_m(start, end)
        if seg_len == 0:
            continue
        travelled = interval_m - carry
        while travelled <= seg_len:
            f = travelled / seg_len
            samples.append(
                (start[0] + (end[0] - start[0]) * f, start[1] + (end[1] - start[1]) * f)
            )
            travelled += interval_m
        carry = (carry + seg_len) % interval_m
    if samples[-1] != line[-1]:
        samples.append(line[-1])
    return samples
