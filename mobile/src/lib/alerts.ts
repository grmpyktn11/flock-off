// Warning the driver about cameras the route could not avoid.
//
// Runs on every GPS tick with no network. The plan response already
// carries the unavoidable cameras, so nothing here needs the backend.

import { Camera } from "../api/types";
import { haversineMeters } from "./geo";
import { LatLng } from "./polyline";

// How far ahead of the camera to speak, in seconds of travel. Long enough
// to lift off the accelerator, short enough that the warning still feels
// connected to the camera it is about.
export const ALERT_LEAD_SECONDS = 15;

// At a standstill the lead distance collapses to nothing and at motorway
// speed it runs away, so it is clamped at both ends.
export const MIN_ALERT_METERS = 150;
export const MAX_ALERT_METERS = 600;

/** How far out to start warning, at this speed. */
export function alertRadiusMeters(speedMps: number): number {
  const lead = Math.max(0, speedMps) * ALERT_LEAD_SECONDS;
  return Math.min(MAX_ALERT_METERS, Math.max(MIN_ALERT_METERS, lead));
}

export type Announcement = {
  camera: Camera;
  distanceMeters: number;
  text: string;
};

/**
 * The camera to warn about now, if any.
 *
 * One warning per camera per trip: `announcedIds` carries the ones already
 * spoken. Repeating them while the driver sits at a light next to one
 * would be worse than saying nothing.
 *
 * Only the nearest qualifying camera is returned. Two warnings talking
 * over each other in a car is noise, and the nearest one is the urgent
 * one anyway.
 */
export function nextAnnouncement(
  position: LatLng,
  speedMps: number,
  cameras: Camera[],
  announcedIds: ReadonlySet<number>
): Announcement | null {
  const radius = alertRadiusMeters(speedMps);

  let best: Announcement | null = null;
  for (const camera of cameras) {
    if (announcedIds.has(camera.id)) continue;
    const distanceMeters = haversineMeters(position, {
      lat: camera.lat,
      lng: camera.lng,
    });
    if (distanceMeters > radius) continue;
    if (best === null || distanceMeters < best.distanceMeters) {
      best = { camera, distanceMeters, text: announcementText(camera, distanceMeters) };
    }
  }
  return best;
}

function announcementText(camera: Camera, distanceMeters: number): string {
  const kind =
    camera.type === "speed_camera" ? "Speed camera" : "License plate reader";
  // Rounded hard: "in about 200 meters" is what a driver can act on, and
  // pretending to 12 metres of precision from a phone GPS is a fiction.
  const rounded = Math.round(distanceMeters / 50) * 50;
  return `${kind} ahead, in about ${rounded} meters.`;
}
