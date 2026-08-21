"""Check a Valhalla build actually avoids our dead zones.

    python infra/valhalla/smoke_test.py --port 8003 \
        --from 38.9076,-77.0723 --to 38.8899,-77.0091

Routes once, drops a dead zone built by the ingestion code onto the
middle of that route, routes again with exclude_polygons, and checks
that the first route crosses the polygon and the second does not.
"""

import argparse
import os
import sys
import time

import requests
from shapely.geometry import LineString

# Run from anywhere: this script lives one directory below the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.deadzone import compute_dead_zone


def decode_polyline6(encoded):
    """Valhalla returns shapes at precision 6, not Google's 5."""
    points, index, lat, lng = [], 0, 0, 0
    while index < len(encoded):
        for is_lat in (True, False):
            result, shift = 0, 0
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
        points.append((lat / 1e6, lng / 1e6))
    return points


def route(url, origin, destination, exclude=None):
    body = {
        "locations": [
            {"lat": origin[0], "lon": origin[1]},
            {"lat": destination[0], "lon": destination[1]},
        ],
        "costing": "auto",
    }
    if exclude:
        body["exclude_polygons"] = exclude

    started = time.time()
    response = requests.post(url, json=body, timeout=60)
    response.raise_for_status()
    trip = response.json()["trip"]
    return (
        decode_polyline6(trip["legs"][0]["shape"]),
        trip["summary"],
        (time.time() - started) * 1000,
    )


def as_linestring(points):
    """Route points are (lat, lng); shapely wants (x, y) = (lng, lat)."""
    return LineString([(p[1], p[0]) for p in points])


def parse_point(text):
    lat, lng = text.split(",")
    return float(lat), float(lng)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8003)
    parser.add_argument("--from", dest="origin", default="38.9076,-77.0723")
    parser.add_argument("--to", dest="destination", default="38.8899,-77.0091")
    args = parser.parse_args(argv)

    url = f"http://localhost:{args.port}/route"
    origin = parse_point(args.origin)
    destination = parse_point(args.destination)

    baseline, summary, ms = route(url, origin, destination)
    print(f"baseline  {summary['length']:.2f} km  {summary['time']:.0f}s  {ms:.0f} ms")

    # Build a dead zone on the route itself, from the stretch of road the
    # route actually uses, so we know the baseline has to cross it.
    third = len(baseline) // 3
    camera = baseline[third]
    road = as_linestring(baseline[third - 3 : third + 4])
    dead_zone = compute_dead_zone(camera[1], camera[0], None, [road])

    ring = [[x, y] for x, y in dead_zone.exterior.coords]
    avoidance, summary2, ms2 = route(url, origin, destination, [ring])
    print(f"avoidance {summary2['length']:.2f} km  {summary2['time']:.0f}s  {ms2:.0f} ms")

    crosses_before = as_linestring(baseline).intersects(dead_zone)
    crosses_after = as_linestring(avoidance).intersects(dead_zone)
    print(f"baseline crosses dead zone : {crosses_before}")
    print(f"avoidance crosses dead zone: {crosses_after}")

    if crosses_before and not crosses_after:
        print("PASS")
        return 0
    print("FAIL: exclude_polygons did not do what we need")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
