// The foreground service: background GPS, spoken camera warnings, and the
// off-route prompt.
//
// Android will not give an app background location without a visible
// foreground service, which is why this exists at all. The task below is
// registered at module load, because Android can restart the process and
// re-deliver locations to a task that must already be defined by then.

import * as Location from "expo-location";
import * as Speech from "expo-speech";
import * as TaskManager from "expo-task-manager";

import { replanRoute } from "../api";
import { nextAnnouncement } from "./alerts";
import { distanceToRouteMeters, haversineMeters } from "./geo";
import { onLocation, isWorthPrompting, recordPromptShown } from "./drift";
import { promptToReplan } from "./notify";
import { decodePolyline, LatLng } from "./polyline";
import { ActiveTrip, endTrip, loadTrip, save } from "./tripStore";

export const LOCATION_TASK = "flock-off-location";

// The spec's ~2s tick. Distance interval as well, so a stationary car
// stops waking the CPU.
const TICK_MS = 2000;
const TICK_METERS = 10;

// Near enough to the destination that the trip is over.
const ARRIVED_METERS = 150;

TaskManager.defineTask(LOCATION_TASK, async ({ data, error }: any) => {
  if (error || !data?.locations?.length) return;
  const last = data.locations[data.locations.length - 1];
  await handleLocation(
    { lat: last.coords.latitude, lng: last.coords.longitude },
    last.coords.speed ?? 0
  );
});

/** What a tick did, for the simulator to display. Ignored in the car. */
export type TickResult = {
  offRouteMeters: number;
  spoke?: string;
  prompted?: boolean;
  arrived?: boolean;
};

/** One GPS tick. Exported so it can be driven directly in a test. */
export async function handleLocation(
  position: LatLng,
  speedMps: number
): Promise<TickResult> {
  const trip = await loadTrip();
  if (!trip) return { offRouteMeters: 0 };

  const offRouteMeters = distanceToRouteMeters(position, trip.route);
  if (await arrivedAt(trip, position)) {
    return { offRouteMeters, arrived: true };
  }

  const spoke = await announceCameras(trip, position, speedMps);
  // One thing at a time in a moving car: a spoken warning and a re-plan
  // prompt in the same tick would collide.
  if (spoke) return { offRouteMeters, spoke };

  const prompted = await checkDrift(trip, position);
  return { offRouteMeters, prompted };
}

async function arrivedAt(trip: ActiveTrip, position: LatLng): Promise<boolean> {
  const toDestination = haversineMeters(position, {
    lat: trip.destination.lat,
    lng: trip.destination.lng,
  });
  if (toDestination > ARRIVED_METERS) return false;
  await stopTrip();
  return true;
}

async function announceCameras(
  trip: ActiveTrip,
  position: LatLng,
  speedMps: number
): Promise<string | undefined> {
  const announcement = nextAnnouncement(
    position,
    speedMps,
    trip.unavoidable,
    new Set(trip.announcedCameraIds)
  );
  if (!announcement) return undefined;

  Speech.speak(announcement.text);
  await save({
    ...trip,
    announcedCameraIds: [...trip.announcedCameraIds, announcement.camera.id],
  });
  return announcement.text;
}

async function checkDrift(trip: ActiveTrip, position: LatLng): Promise<boolean> {
  const tick = onLocation(trip.drift, position, trip.route, Date.now());
  if (!tick.shouldCheck) {
    await save({ ...trip, drift: tick.state });
    return false;
  }

  // Off route for long enough to ask. Whether the driver hears about it
  // depends on the answer: Google reroutes for traffic constantly, and a
  // re-plan that dodges nothing is not worth interrupting them for.
  let drift = tick.state;
  try {
    const plan = await replanRoute(position, trip.destination);
    if (isWorthPrompting(plan.avoidedCount)) {
      await promptToReplan(plan.avoidedCount);
      drift = recordPromptShown(drift);
      await save({
        ...trip,
        drift,
        route: decodePolyline(plan.routePolyline),
        unavoidable: plan.cameras.filter((c) => !c.avoided),
        pendingDeepLink: plan.deepLinkUrl,
      });
      return true;
    }
  } catch {
    // No signal, or the backend is down. The cooldown in the drift state
    // means this will not hammer a dead server.
  }
  await save({ ...trip, drift });
  return false;
}

/** Ask for permissions and start the service. Returns false if refused. */
/** Whether we can already watch the drive. Asks the user nothing. */
export async function canWatchDrive(): Promise<boolean> {
  try {
    const foreground = await Location.getForegroundPermissionsAsync();
    const background = await Location.getBackgroundPermissionsAsync();
    return foreground.granted && background.granted;
  } catch {
    return false;
  }
}

/**
 * Ask for what the warnings need.
 *
 * Deliberately separate from starting a trip. On Android 11 and up the
 * background request does not show a dialog - it sends the user to the
 * system settings page to choose "Allow all the time" themselves. Doing
 * that during the handover hijacks it: the driver taps Start in Google
 * Maps and lands in Settings instead.
 */
export async function requestDrivePermissions(): Promise<boolean> {
  try {
    const foreground = await Location.requestForegroundPermissionsAsync();
    if (!foreground.granted) return false;
    const background = await Location.requestBackgroundPermissionsAsync();
    return background.granted;
  } catch {
    // Expo Go has no background location and throws rather than declining.
    return false;
  }
}

/** Start watching. Does nothing if permission is missing. */
export async function startTripService(): Promise<boolean> {
  try {
    if (!(await canWatchDrive())) return false;
    return await startLocationUpdates();
  } catch {
    return false;
  }
}

async function startLocationUpdates(): Promise<boolean> {
  await Location.startLocationUpdatesAsync(LOCATION_TASK, {
    accuracy: Location.Accuracy.High,
    timeInterval: TICK_MS,
    distanceInterval: TICK_METERS,
    pausesUpdatesAutomatically: false,
    foregroundService: {
      notificationTitle: "Watching for cameras",
      notificationBody: "Tracking your route to warn about cameras ahead.",
      notificationColor: "#1f2937",
    },
  });
  return true;
}

export async function stopTrip(): Promise<void> {
  if (await TaskManager.isTaskRegisteredAsync(LOCATION_TASK)) {
    await Location.stopLocationUpdatesAsync(LOCATION_TASK);
  }
  await endTrip();
}
