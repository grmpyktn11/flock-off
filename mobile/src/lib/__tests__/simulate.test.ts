import { distanceToRouteMeters } from "../geo";
import { LatLng } from "../polyline";
import {
  offsetPerpendicular,
  positionAt,
  routeLengthMeters,
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
