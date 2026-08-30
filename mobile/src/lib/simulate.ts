// Route geometry helpers: length, position along, and sideways offset.
// Used by the mock backend to place cameras on a generated route and by
// the trip machinery to reason about positions.

import { haversineMeters } from "./geo";
import { LatLng } from "./polyline";

export function routeLengthMeters(route: LatLng[]): number {
  let total = 0;
  for (let i = 0; i < route.length - 1; i++) {
    total += haversineMeters(route[i], route[i + 1]);
  }
  return total;
}

/** The point this far along the route, interpolated within a segment. */
export function positionAt(route: LatLng[], distanceM: number): LatLng {
  if (route.length === 0) throw new Error("empty route");
  if (route.length === 1 || distanceM <= 0) return route[0];

  let remaining = distanceM;
  for (let i = 0; i < route.length - 1; i++) {
    const segment = haversineMeters(route[i], route[i + 1]);
    if (remaining <= segment) {
      const t = segment === 0 ? 0 : remaining / segment;
      return {
        lat: route[i].lat + (route[i + 1].lat - route[i].lat) * t,
        lng: route[i].lng + (route[i + 1].lng - route[i].lng) * t,
      };
    }
    remaining -= segment;
  }
  return route[route.length - 1];
}

/** The same point pushed sideways, for faking a wrong turn. */
export function offsetPerpendicular(
  route: LatLng[],
  distanceM: number,
  meters: number
): LatLng {
  const here = positionAt(route, distanceM);
  const ahead = positionAt(route, distanceM + 50);
  const dLat = ahead.lat - here.lat;
  const dLng = ahead.lng - here.lng;
  const length = Math.hypot(dLat, dLng);
  if (length === 0) return here;

  // Rotate the heading 90 degrees and scale it to the offset we want.
  const perpLat = -dLng / length;
  const perpLng = dLat / length;
  const degreesPerMeter = 1 / 111320;
  return {
    lat: here.lat + perpLat * meters * degreesPerMeter,
    lng:
      here.lng +
      (perpLng * meters * degreesPerMeter) /
        Math.cos((here.lat * Math.PI) / 180),
  };
}

