// The trip in progress, on disk.
//
// The location task runs headless: Android wakes it while the app is
// backgrounded and Google Maps is in front, and it gets no access to
// React state. So everything it needs lives here, and everything it
// learns goes back here.

import AsyncStorage from "@react-native-async-storage/async-storage";

import { Camera, Place } from "../api/types";
import { DriftState, initialDriftState } from "./drift";
import { LatLng } from "./polyline";

const KEY = "activeTrip";

export type ActiveTrip = {
  destination: Place;
  // The route Google said it would drive, decoded. Drift is measured
  // against this.
  route: LatLng[];
  // Cameras the route could not avoid, the ones worth speaking about.
  unavoidable: Camera[];
  announcedCameraIds: number[];
  drift: DriftState;
  startedAtMs: number;
  // For the stationary timeout. A trip nobody ended should not keep a
  // foreground service and the GPS alive all night.
  lastPosition: LatLng | null;
  lastMovedAtMs: number;
  // Set when an off-route prompt is showing. Deciding whether to prompt
  // already cost a re-plan, so the link it produced is kept here and the
  // notification action fires it without asking again.
  pendingDeepLink?: string;
};

export async function startTrip(
  destination: Place,
  route: LatLng[],
  unavoidable: Camera[]
): Promise<ActiveTrip> {
  const trip: ActiveTrip = {
    destination,
    route,
    unavoidable,
    announcedCameraIds: [],
    drift: initialDriftState,
    startedAtMs: Date.now(),
    lastPosition: null,
    lastMovedAtMs: Date.now(),
  };
  await save(trip);
  return trip;
}

export async function loadTrip(): Promise<ActiveTrip | null> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as ActiveTrip) : null;
  } catch {
    // A trip we cannot read is a trip we cannot drive. Treat it as absent
    // rather than crashing a background task nobody is watching.
    return null;
  }
}

export async function save(trip: ActiveTrip): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, JSON.stringify(trip));
  } catch {
    // Losing one tick's state costs a repeated announcement at worst.
  }
}

export async function endTrip(): Promise<void> {
  try {
    await AsyncStorage.removeItem(KEY);
  } catch {
    // Nothing useful to do; the next startTrip overwrites it anyway.
  }
}
