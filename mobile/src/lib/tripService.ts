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

// A trip that has not moved this far in this long is over, whether or not
// the driver ever arrived. Someone who abandons a trip, or plans one and
// never drives it, should not be left with a foreground service and the
// GPS running until they notice the notification.
const STATIONARY_METERS = 80;
const STATIONARY_LIMIT_MS = 10 * 60 * 1000;

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
  let trip = await loadTrip();
  if (!trip) return { offRouteMeters: 0 };

  const offRouteMeters = distanceToRouteMeters(position, trip.route);
  if (await arrivedAt(trip, position)) {
    return { offRouteMeters, arrived: true };
  }

  const moved =
    !trip.lastPosition ||
    haversineMeters(position, trip.lastPosition) > STATIONARY_METERS;
  const now = Date.now();
  if (!moved && now - trip.lastMovedAtMs > STATIONARY_LIMIT_MS) {
    await stopTrip();
    return { offRouteMeters, arrived: true };
  }
  trip = {
    ...trip,
    lastPosition: position,
    lastMovedAtMs: moved ? now : trip.lastMovedAtMs,
  };

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
/**
 * Is a trip actually running right now?
 *
 * The stored trip and the running service can fall out of step: swiping
 * the app out of recents kills the service, and Android can kill it under
 * memory pressure, but neither clears what is on disk. So a trip with no
 * service behind it is finished, whatever the disk says, and the app
 * should not offer to stop something that already stopped.
 */
export async function reconcileTrip(): Promise<boolean> {
  const trip = await loadTrip();
  if (!trip) return false;

  if (!(await isWatching())) {
    await endTrip();
    return false;
  }
  return true;
}

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
      notificationBody: "Tap to open flock-off and stop.",
      notificationColor: "#1f2937",
      // Swiping the app out of recents ends the trip. Switching away
      // does not, which is the distinction that matters: during a drive
      // Google Maps is in front and this app is backgrounded, and the
      // warnings have to keep coming. Someone clearing it out of recents
      // is finished.
      killServiceOnDestroy: true,
    },
  });
  return true;
}

/**
 * Are location updates actually running?
 *
 * Not the same question as whether the task is registered. defineTask
 * registers it at module load and it stays registered whether or not
 * anything is watching, so TaskManager answers yes long after the
 * service has gone - and then stopping it throws TaskNotFoundException,
 * because the Location module disagrees. Ask the module that owns the
 * answer.
 */
async function isWatching(): Promise<boolean> {
  try {
    return await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK);
  } catch {
    return false;
  }
}

export async function stopTrip(): Promise<void> {
  try {
    if (await isWatching()) {
      await Location.stopLocationUpdatesAsync(LOCATION_TASK);
    }
  } catch {
    // Stopping something already stopped is the outcome we wanted.
    // Android can kill the service out from under us at any moment, so
    // this race is normal rather than exceptional.
  }
  await endTrip();
}
