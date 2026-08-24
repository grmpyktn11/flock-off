// The offline demo path. With EXPO_PUBLIC_API_URL unset the whole app runs
// on this module, so if the mock plan is not drivable there is nothing to
// record and no way to show the app without a server.

import { planRoute } from "../mockBackend";
import { Place } from "../types";
import { nextAnnouncement } from "../../lib/alerts";
import { distanceToRouteMeters, haversineMeters } from "../../lib/geo";
import { decodePolyline, encodePolyline } from "../../lib/polyline";
import { positionAt, routeLengthMeters } from "../../lib/simulate";

const RESTON: Place = {
  placeId: "mock-reston-town-center",
  name: "Reston Town Center",
  address: "",
  lat: 38.9586,
  lng: -77.3571,
};

const VIENNA: Place = {
  placeId: "mock-vienna-metro",
  name: "Vienna Metro Station",
  address: "",
  lat: 38.8776,
  lng: -77.2719,
};

test("a polyline survives a round trip", () => {
  const points = [
    { lat: 38.9586, lng: -77.3571 },
    { lat: 38.9127, lng: -77.3184 },
    { lat: 38.8776, lng: -77.2719 },
  ];
  const back = decodePolyline(encodePolyline(points));
  expect(back).toHaveLength(points.length);
  back.forEach((point, i) => {
    expect(point.lat).toBeCloseTo(points[i].lat, 5);
    expect(point.lng).toBeCloseTo(points[i].lng, 5);
  });
});

test("the mock route is real geometry, not a placeholder", async () => {
  const plan = await planRoute(RESTON, VIENNA);
  const route = decodePolyline(plan.routePolyline);

  // The old mock returned "mock_polyline", which decoded to a single point
  // at latitude 8697 and made every simulated drive finish instantly.
  expect(route.length).toBeGreaterThan(50);
  for (const point of route) {
    expect(Math.abs(point.lat)).toBeLessThan(90);
  }

  const straight = haversineMeters(RESTON, VIENNA);
  const along = routeLengthMeters(route);
  expect(along).toBeGreaterThan(straight);
  expect(along).toBeLessThan(straight * 1.5);
});

test("avoided cameras are off the route and unavoidable ones are on it", async () => {
  const plan = await planRoute(RESTON, VIENNA);
  const route = decodePolyline(plan.routePolyline);

  expect(plan.avoidedCount).toBe(3);
  expect(plan.unavoidableCount).toBe(1);

  for (const camera of plan.cameras) {
    const distance = distanceToRouteMeters(
      { lat: camera.lat, lng: camera.lng },
      route
    );
    if (camera.avoided) {
      expect(distance).toBeGreaterThan(200);
    } else {
      expect(distance).toBeLessThan(10);
    }
  }
});

test("driving the mock route announces the unavoidable camera once", async () => {
  const plan = await planRoute(RESTON, VIENNA);
  const route = decodePolyline(plan.routePolyline);
  const total = routeLengthMeters(route);
  const unavoidable = plan.cameras.filter((camera) => !camera.avoided);

  const announced = new Set<number>();
  const spoken: string[] = [];
  const speedMps = 25;

  for (let travelled = 0; travelled <= total; travelled += 10) {
    const announcement = nextAnnouncement(
      positionAt(route, travelled),
      speedMps,
      unavoidable,
      announced
    );
    if (announcement) {
      announced.add(announcement.camera.id);
      spoken.push(announcement.text);
    }
  }

  expect(spoken).toHaveLength(1);
  expect(spoken[0]).toMatch(/License plate reader ahead, in about \d+ meters\./);
});

test("the detour costs time, and the numbers agree with each other", async () => {
  const plan = await planRoute(RESTON, VIENNA);
  expect(plan.etaDeltaSeconds).toBeGreaterThan(0);
  expect(plan.routeEtaSeconds - plan.baselineEtaSeconds).toBe(
    plan.etaDeltaSeconds
  );
});
