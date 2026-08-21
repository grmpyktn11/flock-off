import { distanceToRouteMeters } from "../geo";
import { LatLng } from "../polyline";
import {
  offsetPerpendicular,
  positionAt,
  routeLengthMeters,
  simulateDrive,
} from "../simulate";

const ROUTE: LatLng[] = [
  { lat: 38.86, lng: -77.32 },
  { lat: 38.86, lng: -77.31 },
  { lat: 38.86, lng: -77.3 },
];

describe("positionAt", () => {
  it("interpolates inside a segment rather than snapping to vertices", () => {
    const total = routeLengthMeters(ROUTE);
    const middle = positionAt(ROUTE, total / 2);
    expect(middle.lng).toBeCloseTo(-77.31, 4);
    expect(distanceToRouteMeters(middle, ROUTE)).toBeLessThan(1);
  });

  it("clamps at both ends", () => {
    expect(positionAt(ROUTE, -100)).toEqual(ROUTE[0]);
    expect(positionAt(ROUTE, 1e9)).toEqual(ROUTE[2]);
  });
});

describe("offsetPerpendicular", () => {
  it("pushes the driver off the route by roughly the distance asked for", () => {
    const off = offsetPerpendicular(ROUTE, 400, 300);
    const distance = distanceToRouteMeters(off, ROUTE);
    expect(distance).toBeGreaterThan(250);
    expect(distance).toBeLessThan(350);
  });
});

describe("simulateDrive", () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it("walks the route and stops at the end", () => {
    const seen: LatLng[] = [];
    const onFinish = jest.fn();
    simulateDrive({
      route: ROUTE,
      speedMps: 100,
      tickMs: 1000,
      onTick: (p) => void seen.push(p),
      onFinish,
    });

    jest.advanceTimersByTime(60_000);
    expect(seen.length).toBeGreaterThan(5);
    expect(onFinish).toHaveBeenCalled();
    // Every tick sits on the route when nothing is veering it off.
    expect(Math.max(...seen.map((p) => distanceToRouteMeters(p, ROUTE)))).toBeLessThan(1);
  });

  it("veers off once past the given fraction", () => {
    const seen: LatLng[] = [];
    simulateDrive({
      route: ROUTE,
      speedMps: 100,
      tickMs: 1000,
      veerMeters: 300,
      veerAfterFraction: 0.5,
      onTick: (p) => void seen.push(p),
    });

    jest.advanceTimersByTime(60_000);
    const distances = seen.map((p) => distanceToRouteMeters(p, ROUTE));
    expect(distances[0]).toBeLessThan(1);
    expect(Math.max(...distances)).toBeGreaterThan(250);
  });
});
