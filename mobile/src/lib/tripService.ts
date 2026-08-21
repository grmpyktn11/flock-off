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

/** One GPS tick. Exported so it can be driven directly in a test. */
export async function handleLocation(position: LatLng, speedMps: number): Promise<void> {
  const trip = await loadTrip();
  if (!trip) return;

  if (await arrivedAt(trip, position)) return;
  const spoke = await announceCameras(trip, position, speedMps);
  // One thing at a time in a moving car: a spoken warning and a re-plan
  // prompt in the same tick would collide.
  if (!spoke) await checkDrift(trip, position);
}

async function arrivedAt(trip: ActiveTrip, position: LatLng): Promise<boolean> {
  const { haversineMeters } = await import("./geo");
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
): Promise<boolean> {
  const announcement = nextAnnouncement(
    position,
    speedMps,
    trip.unavoidable,
    new Set(trip.announcedCameraIds)
  );
  if (!announcement) return false;

  Speech.speak(announcement.text);
  await save({
    ...trip,
    announcedCameraIds: [...trip.announcedCameraIds, announcement.camera.id],
  });
  return true;
}

async function checkDrift(trip: ActiveTrip, position: LatLng): Promise<void> {
  const tick = onLocation(trip.drift, position, trip.route, Date.now());
  if (!tick.shouldCheck) {
    await save({ ...trip, drift: tick.state });
    return;
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
      return;
    }
  } catch {
    // No signal, or the backend is down. The cooldown in the drift state
    // means this will not hammer a dead server.
  }
  await save({ ...trip, drift });
}

/** Ask for permissions and start the service. Returns false if refused. */
export async function startTripService(): Promise<boolean> {
  const foreground = await Location.requestForegroundPermissionsAsync();
  if (!foreground.granted) return false;
  const background = await Location.requestBackgroundPermissionsAsync();
  if (!background.granted) return false;

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
