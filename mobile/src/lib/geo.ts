// Distance maths for drift detection. All of it runs on the phone every
// GPS tick with no network, so it stays cheap and dependency-free.

import { LatLng } from "./polyline";

const EARTH_RADIUS_M = 6371008.8;

export function haversineMeters(a: LatLng, b: LatLng): number {
  const dLat = toRadians(b.lat - a.lat);
  const dLng = toRadians(b.lng - a.lng);
  const lat1 = toRadians(a.lat);
  const lat2 = toRadians(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h));
}

/**
 * Shortest distance from a point to a route, in metres.
 *
 * Distance to the nearest *segment*, not the nearest vertex. A route
 * encoded every hundred metres or so has vertices far apart on a straight
 * road, and nearest-vertex would read as off-route halfway between two of
 * them.
 */
export function distanceToRouteMeters(point: LatLng, route: LatLng[]): number {
  if (route.length === 0) return Infinity;
  if (route.length === 1) return haversineMeters(point, route[0]);

  let nearest = Infinity;
  for (let i = 0; i < route.length - 1; i++) {
    const d = distanceToSegmentMeters(point, route[i], route[i + 1]);
    if (d < nearest) nearest = d;
  }
  return nearest;
}

function distanceToSegmentMeters(p: LatLng, a: LatLng, b: LatLng): number {
  // Flat-earth projection centred on the point. Over the few hundred
  // metres that matter here the error is far below GPS noise, and it
  // turns the problem into plane geometry.
  const [px, py] = project(p, p);
  const [ax, ay] = project(a, p);
  const [bx, by] = project(b, p);

  const dx = bx - ax;
  const dy = by - ay;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared === 0) return Math.hypot(px - ax, py - ay);

  // Clamped so the nearest point stays on the segment rather than running
  // off the end of the line it sits on.
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSquared));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

function project(point: LatLng, origin: LatLng): [number, number] {
  const x =
    toRadians(point.lng - origin.lng) *
    EARTH_RADIUS_M *
    Math.cos(toRadians(origin.lat));
  const y = toRadians(point.lat - origin.lat) * EARTH_RADIUS_M;
  return [x, y];
}

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}
