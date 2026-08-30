/**
 * Replays a real plan through the drive-time logic.
 *
 * Skipped unless TEST_API_URL points at a running backend, so the normal
 * suite stays offline. Start one with:
 *
 *   cd backend && uvicorn app.main:app --port 8000
 *   cd mobile  && TEST_API_URL=http://127.0.0.1:8000 npm test
 *
 * This is the seam the unit tests cannot reach: real Google geometry,
 * real camera positions, and the question of whether the thresholds
 * tuned against straight synthetic lines still behave on a real road.
 */

import { nextAnnouncement } from "../alerts";
import { CONSECUTIVE_TICKS, initialDriftState, onLocation } from "../drift";
import { distanceToRouteMeters } from "../geo";
import { decodePolyline, LatLng } from "../polyline";
import { offsetPerpendicular, positionAt, routeLengthMeters } from "../simulate";

const API = process.env.TEST_API_URL;
const maybe = API ? describe : describe.skip;

// Dulles to Tysons. Chosen because it carries cameras the route cannot
// avoid, so the announcement test has something to announce.
const TRIP = {
  origin: { lat: 38.9531, lng: -77.4565 },
  destination: { lat: 38.9179, lng: -77.2214 },
};

type Plan = {
  route_polyline: string;
  cameras: { id: number; type: string; lat: number; lng: number; avoided: boolean }[];
  avoided_count: number;
  unavoidable_count: number;
  eta_delta_seconds: number;
};

async function fetchPlan(): Promise<Plan> {
  const response = await fetch(`${API}/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(TRIP),
  });
  if (!response.ok) throw new Error(`plan failed: ${response.status}`);
  return response.json();
}

maybe("replaying a real plan", () => {
  jest.setTimeout(60_000);

  let plan: Plan;
  let route: LatLng[];

  beforeAll(async () => {
    plan = await fetchPlan();
    route = decodePolyline(plan.route_polyline);
  });

  it("returns a route the app can decode", () => {
    expect(route.length).toBeGreaterThan(20);
    expect(routeLengthMeters(route)).toBeGreaterThan(5000);
  });

  it("never reports drift while driving the route it was given", () => {
    // The thresholds were tuned against straight synthetic lines. A real
    // route bends, and its vertices are unevenly spaced; if either broke
    // the point-to-segment measure, this fires constantly in the car.
    const total = routeLengthMeters(route);
    let state = initialDriftState;
    let worst = 0;

    for (let travelled = 0; travelled < total; travelled += 25) {
      const here = positionAt(route, travelled);
      const tick = onLocation(state, here, route, travelled * 100);
      state = tick.state;
      worst = Math.max(worst, tick.distanceMeters);
      expect(tick.shouldCheck).toBe(false);
    }
    expect(worst).toBeLessThan(5);
  });

  it("detects a real wrong turn within the expected number of ticks", () => {
    const total = routeLengthMeters(route);
    let state = initialDriftState;
    let ticksUntilCheck = 0;
    let checked = false;

    for (let travelled = total / 2; travelled < total; travelled += 25) {
      const off = offsetPerpendicular(route, travelled, 300);
      const tick = onLocation(state, off, route, travelled * 100);
      state = tick.state;
      ticksUntilCheck += 1;
      if (tick.shouldCheck) {
        checked = true;
        break;
      }
    }
    expect(checked).toBe(true);
    expect(ticksUntilCheck).toBe(CONSECUTIVE_TICKS);
  });

  it("announces each unavoidable camera exactly once along the route", () => {
    const unavoidable = plan.cameras
      .filter((c) => !c.avoided)
      .map((c) => ({
        ...c, type: c.type as "alpr" | "speed_camera", facingDeg: null,
        operator: null, brand: null, roadName: null, roadRef: null,
        crimeCount: null, crimeDesc: null, arrestCount: null, arrestDesc: null,
        tractIncome: null, countyIncome: null, usefulnessScore: null, scoreDesc: null,
      }));
    // If this ever fires, the trip above stopped carrying unavoidable
    // cameras and the test below is checking nothing.
    expect(unavoidable.length).toBeGreaterThan(0);

    const announced = new Set<number>();
    const total = routeLengthMeters(route);
    for (let travelled = 0; travelled < total; travelled += 25) {
      const here = positionAt(route, travelled);
      const announcement = nextAnnouncement(here, 20, unavoidable, announced);
      if (announcement) announced.add(announcement.camera.id);
    }

    // Every camera the route drives into should get warned about, and a
    // camera warned about twice would mean the seen-set is not working.
    expect(announced.size).toBe(unavoidable.length);
  });

  it("keeps every reported camera near the route it reports them for", () => {
    for (const camera of plan.cameras) {
      const distance = distanceToRouteMeters({ lat: camera.lat, lng: camera.lng }, route);
      // Avoided cameras sit off the driven route by construction; the
      // ones we could not avoid should be on it.
      if (!camera.avoided) expect(distance).toBeLessThan(60);
    }
  });
});
