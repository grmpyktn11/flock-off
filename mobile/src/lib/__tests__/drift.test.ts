import { distanceToRouteMeters } from "../geo";
import { decodePolyline, LatLng } from "../polyline";
import {
  CHECK_COOLDOWN_MS,
  MAX_PROMPTS_PER_TRIP,
  OFF_ROUTE_METERS,
  initialDriftState,
  isWorthPrompting,
  onLocation,
  recordPromptShown,
} from "../drift";

// A straight run east along Fairfax Boulevard, vertices ~500m apart.
const ROUTE: LatLng[] = [
  { lat: 38.86, lng: -77.32 },
  { lat: 38.86, lng: -77.315 },
  { lat: 38.86, lng: -77.31 },
];

const TICK = 2000; // the spec's ~2s GPS tick

function driveOffRoute(ticks: number, startMs = 0) {
  let state = initialDriftState;
  let last;
  for (let i = 0; i < ticks; i++) {
    last = onLocation(state, { lat: 38.87, lng: -77.315 }, ROUTE, startMs + i * TICK);
    state = last.state;
  }
  return last!;
}

describe("distanceToRouteMeters", () => {
  it("measures to the nearest segment, not the nearest vertex", () => {
    // Exactly between two vertices, 0m off the line. Nearest-vertex would
    // report ~220m here and read as off-route on a perfectly good road.
    const between = { lat: 38.86, lng: -77.3175 };
    expect(distanceToRouteMeters(between, ROUTE)).toBeLessThan(1);
  });

  it("measures perpendicular offset from the route", () => {
    const north = { lat: 38.8609, lng: -77.315 }; // ~100m north
    const d = distanceToRouteMeters(north, ROUTE);
    expect(d).toBeGreaterThan(90);
    expect(d).toBeLessThan(110);
  });

  it("does not run off the end of a segment", () => {
    // Well past the eastern end. Clamping to the segment means this is
    // measured from the endpoint, not from an infinite line.
    const past = { lat: 38.86, lng: -77.29 };
    expect(distanceToRouteMeters(past, ROUTE)).toBeGreaterThan(1500);
  });
});

describe("onLocation", () => {
  it("stays quiet while on the route", () => {
    const tick = onLocation(initialDriftState, ROUTE[1], ROUTE, 0);
    expect(tick.shouldCheck).toBe(false);
    expect(tick.state.consecutiveOffRoute).toBe(0);
  });

  it("waits for three consecutive ticks before checking", () => {
    expect(driveOffRoute(1).shouldCheck).toBe(false);
    expect(driveOffRoute(2).shouldCheck).toBe(false);
    expect(driveOffRoute(3).shouldCheck).toBe(true);
  });

  it("resets when the driver rejoins the route", () => {
    let state = driveOffRoute(2).state;
    state = onLocation(state, ROUTE[1], ROUTE, 10_000).state;
    expect(state.consecutiveOffRoute).toBe(0);

    // A later excursion earns its own three ticks rather than firing on one.
    const tick = onLocation(state, { lat: 38.87, lng: -77.315 }, ROUTE, 12_000);
    expect(tick.shouldCheck).toBe(false);
  });

  it("does not check again until the cooldown expires", () => {
    const first = driveOffRoute(3);
    expect(first.shouldCheck).toBe(true);

    let state = first.state;
    const soon = onLocation(state, { lat: 38.87, lng: -77.315 }, ROUTE, 30_000);
    expect(soon.shouldCheck).toBe(false);

    // The cooldown runs from the tick that triggered the check, not from
    // the start of the trip.
    const checkedAt = first.state.lastCheckAtMs!;
    const later = onLocation(
      soon.state,
      { lat: 38.87, lng: -77.315 },
      ROUTE,
      checkedAt + CHECK_COOLDOWN_MS
    );
    expect(later.shouldCheck).toBe(true);
  });

  it("stops checking once the per-trip prompt cap is reached", () => {
    let state = initialDriftState;
    for (let i = 0; i < MAX_PROMPTS_PER_TRIP; i++) state = recordPromptShown(state);

    let last;
    for (let i = 0; i < 5; i++) {
      last = onLocation(state, { lat: 38.87, lng: -77.315 }, ROUTE, i * TICK);
      state = last.state;
    }
    expect(last!.shouldCheck).toBe(false);
  });

  it("treats exactly the threshold as still on route", () => {
    const tick = onLocation(initialDriftState, ROUTE[0], ROUTE, 0);
    expect(tick.distanceMeters).toBeLessThanOrEqual(OFF_ROUTE_METERS);
    expect(tick.shouldCheck).toBe(false);
  });
});

describe("isWorthPrompting", () => {
  it("stays silent when a re-plan would avoid nothing", () => {
    // Google reroutes for traffic constantly. If its path is already as
    // clean as ours, interrupting the driver teaches them to dismiss us.
    expect(isWorthPrompting(0)).toBe(false);
  });

  it("prompts when there are cameras to dodge", () => {
    expect(isWorthPrompting(1)).toBe(true);
  });
});

describe("decodePolyline", () => {
  it("round-trips a route the backend encoded", () => {
    // "_p~iF~ps|U_ulLnnqC_mqNvxq`@" is the canonical Google example.
    const points = decodePolyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@");
    expect(points).toHaveLength(3);
    expect(points[0].lat).toBeCloseTo(38.5, 5);
    expect(points[0].lng).toBeCloseTo(-120.2, 5);
    expect(points[2].lat).toBeCloseTo(43.252, 5);
    expect(points[2].lng).toBeCloseTo(-126.453, 5);
  });
});
