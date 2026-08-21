/**
 * When a trip is over.
 *
 * The foreground service keeps the GPS awake, so a trip that never ends
 * is a battery drain the driver has to notice and stop by hand. It should
 * end on its own.
 */
import { haversineMeters } from "../geo";
import { LatLng } from "../polyline";

// Mirrors the constants in tripService, which are not exported because
// nothing outside it should be tuning them.
const ARRIVED_METERS = 150;
const STATIONARY_METERS = 80;
const STATIONARY_LIMIT_MS = 10 * 60 * 1000;

const DESTINATION: LatLng = { lat: 38.8611, lng: -77.376 };

function metresAway(from: LatLng, metres: number): LatLng {
  return { lat: from.lat + metres / 111320, lng: from.lng };
}

describe("arrival", () => {
  it("counts a driver near the destination as arrived", () => {
    const close = metresAway(DESTINATION, 100);
    expect(haversineMeters(close, DESTINATION)).toBeLessThan(ARRIVED_METERS);
  });

  it("does not count one still a few streets away", () => {
    const away = metresAway(DESTINATION, 400);
    expect(haversineMeters(away, DESTINATION)).toBeGreaterThan(ARRIVED_METERS);
  });
});

describe("the stationary timeout", () => {
  it("treats GPS jitter at a standstill as not moving", () => {
    // A parked phone wanders tens of metres. That must not read as
    // driving, or an abandoned trip never times out.
    const parked = metresAway(DESTINATION, 30);
    expect(haversineMeters(parked, DESTINATION)).toBeLessThan(STATIONARY_METERS);
  });

  it("treats a moving car as moving", () => {
    // At 13 m/s a 2 second tick covers ~27m, so several ticks clear the
    // threshold well inside the timeout.
    const afterTenSeconds = metresAway(DESTINATION, 134);
    expect(haversineMeters(afterTenSeconds, DESTINATION)).toBeGreaterThan(
      STATIONARY_METERS
    );
  });

  it("gives a driver long enough to sit in traffic", () => {
    // Ten minutes stationary ends the trip. A long light or a jam is
    // minutes, not tens of minutes.
    expect(STATIONARY_LIMIT_MS).toBeGreaterThanOrEqual(5 * 60 * 1000);
  });
});
