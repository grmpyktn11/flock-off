import { Camera } from "../../api/types";
import {
  MAX_ALERT_METERS,
  MIN_ALERT_METERS,
  alertRadiusMeters,
  nextAnnouncement,
} from "../alerts";

const HERE = { lat: 38.86, lng: -77.32 };

function cameraAt(id: number, metersEast: number, type: Camera["type"] = "alpr"): Camera {
  // ~1 degree of longitude is 111320*cos(38.86) metres here.
  const degrees = metersEast / (111320 * Math.cos((38.86 * Math.PI) / 180));
  return { id, type, lat: HERE.lat, lng: HERE.lng + degrees, facingDeg: null, avoided: false };
}

describe("alertRadiusMeters", () => {
  it("scales with speed", () => {
    expect(alertRadiusMeters(20)).toBeGreaterThan(alertRadiusMeters(10));
  });

  it("does not collapse to nothing when stopped", () => {
    expect(alertRadiusMeters(0)).toBe(MIN_ALERT_METERS);
  });

  it("does not run away at motorway speed", () => {
    expect(alertRadiusMeters(45)).toBe(MAX_ALERT_METERS);
  });
});

describe("nextAnnouncement", () => {
  it("says nothing when the nearest camera is out of range", () => {
    const far = [cameraAt(1, 5000)];
    expect(nextAnnouncement(HERE, 15, far, new Set())).toBeNull();
  });

  it("warns about a camera inside the radius", () => {
    const near = [cameraAt(1, 200)];
    const announcement = nextAnnouncement(HERE, 15, near, new Set());
    expect(announcement?.camera.id).toBe(1);
    expect(announcement?.text).toContain("License plate reader");
    expect(announcement?.text).toContain("200 meters");
  });

  it("names a speed camera as a speed camera", () => {
    const near = [cameraAt(1, 100, "speed_camera")];
    expect(nextAnnouncement(HERE, 15, near, new Set())?.text).toContain("Speed camera");
  });

  it("warns about the nearest one only", () => {
    // Two warnings talking over each other in a car is noise. 30 m/s puts
    // the radius at 450m so both are genuinely in range and the test is
    // about the choice, not about one being too far away.
    const both = [cameraAt(1, 400), cameraAt(2, 150)];
    expect(alertRadiusMeters(30)).toBeGreaterThan(400);
    expect(nextAnnouncement(HERE, 30, both, new Set())?.camera.id).toBe(2);
  });

  it("does not repeat a camera already announced", () => {
    // Otherwise sitting at a light beside one would talk continuously.
    const near = [cameraAt(1, 200)];
    expect(nextAnnouncement(HERE, 15, near, new Set([1]))).toBeNull();
  });

  it("moves on to the next camera once the first is announced", () => {
    const both = [cameraAt(1, 150), cameraAt(2, 400)];
    const second = nextAnnouncement(HERE, 30, both, new Set([1]));
    expect(second?.camera.id).toBe(2);
  });
});
