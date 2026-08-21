// Replaying a drive without driving.
//
// Feeds synthetic positions into the same handler the GPS task calls, so
// warnings, drift detection, the re-plan prompt and the trip store all
// run for real. What it cannot exercise is the layer underneath: whether
// Android actually delivers locations to a backgrounded task, and whether
// the foreground service survives. Those need a real device moving, or a
// mock location app. See docs/testing-the-drive.md.

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

export type SimulationOptions = {
  route: LatLng[];
  speedMps?: number;
  tickMs?: number;
  /** Push the driver this far off the route, to trigger drift detection. */
  veerMeters?: number;
  /** Start veering once this fraction of the route is behind us. */
  veerAfterFraction?: number;
  onTick: (position: LatLng, speedMps: number) => unknown;
  onFinish?: () => void;
};

/** Drive the route. Returns a function that stops it early. */
export function simulateDrive(options: SimulationOptions): () => void {
  const {
    route,
    speedMps = 13.4,
    tickMs = 2000,
    veerMeters = 0,
    veerAfterFraction = 0.5,
    onTick,
    onFinish,
  } = options;

  const total = routeLengthMeters(route);
  const veerAfter = total * veerAfterFraction;
  let travelled = 0;

  const timer = setInterval(() => {
    travelled += speedMps * (tickMs / 1000);
    if (travelled >= total) {
      clearInterval(timer);
      void onTick(positionAt(route, total), speedMps);
      onFinish?.();
      return;
    }
    const position =
      veerMeters > 0 && travelled >= veerAfter
        ? offsetPerpendicular(route, travelled, veerMeters)
        : positionAt(route, travelled);
    void onTick(position, speedMps);
  }, tickMs);

  return () => clearInterval(timer);
}
