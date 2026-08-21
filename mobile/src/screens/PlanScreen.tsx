import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { ActivityIndicator, Button, Divider, List, Snackbar } from "react-native-paper";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { RootStackParamList } from "../../App";
import { ApiError, Camera, Plan, planRoute } from "../api";
import { openInGoogleMaps } from "../lib/googleMaps";
import { haversineMeters } from "../lib/geo";
import { decodePolyline } from "../lib/polyline";
import { loadTrip, startTrip } from "../lib/tripStore";
import {
  TickResult,
  canWatchDrive,
  handleLocation,
  requestDrivePermissions,
  startTripService,
  stopTrip,
} from "../lib/tripService";
import { simulateDrive } from "../lib/simulate";

type Props = NativeStackScreenProps<RootStackParamList, "Plan">;

export default function PlanScreen({ route }: Props) {
  const { origin, destination, strict } = route.params;
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState("");
  const [simulating, setSimulating] = useState(false);
  const [tick, setTick] = useState<TickResult | null>(null);
  const [canWarn, setCanWarn] = useState(true);
  const [watching, setWatching] = useState(false);
  const insets = useSafeAreaInsets();

  useEffect(() => {
    canWatchDrive().then(setCanWarn);
    // A trip survives the app being closed, so coming back to this screen
    // has to reflect one that is already running.
    loadTrip().then((trip) => setWatching(trip !== null));
  }, []);

  useEffect(() => {
    let cancelled = false;
    planRoute(origin, destination, strict)
      .then((result) => {
        if (!cancelled) {
          setPlan(result);
        }
      })
      .catch((cause) => {
        if (!cancelled) {
          setError(
            cause instanceof ApiError
              ? cause.message
              : "Could not plan a route. Try again."
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [origin, destination, strict]);

  async function startNavigation() {
    // Development only. Replays the planned route through the same handler
  // the GPS task calls, so warnings, drift and the re-plan prompt all run
  // without leaving the desk. Stripped from release builds.
  async function endTrip() {
    await stopTrip();
    setWatching(false);
    setTick(null);
  }

  async function enableWarnings() {
    const granted = await requestDrivePermissions();
    setCanWarn(granted);
    if (!granted) {
      setError("Warnings need location access set to Allow all the time.");
    }
  }

  async function simulate(veerMeters: number) {
    if (plan === null || simulating) {
      return;
    }
    const route = decodePolyline(plan.routePolyline);
    await startTrip(destination, route, plan.cameras.filter((c) => !c.avoided));
    setSimulating(true);
    setTick(null);
    simulateDrive({
      route,
      veerMeters,
      speedMps: 25,
      tickMs: 400,
      onTick: async (position, speedMps) => {
        const result = await handleLocation(position, speedMps);
        // Announcements and prompts are worth keeping on screen; a plain
        // tick only updates the distance readout.
        setTick((previous) =>
          result.spoke || result.prompted || result.arrived
            ? result
            : { ...result, spoke: previous?.spoke, prompted: previous?.prompted }
        );
      },
      onFinish: () => setSimulating(false),
    });
  }

  if (plan === null) {
      return;
    }

    // Record the trip before handing over. Once Google Maps is in front
    // this app is backgrounded, and the location task reads everything it
    // needs from storage.
    const unavoidable = plan.cameras.filter((camera) => !camera.avoided);
    await startTrip(destination, decodePolyline(plan.routePolyline), unavoidable);

    // Starts only if permission is already granted. Asking here would
    // hijack the handover: on Android 11 and up the background request
    // opens the system settings page instead of showing a dialog, so the
    // driver taps this button and lands in Settings rather than Maps.
    await startTripService();
    setWatching(true);

    try {
      await openInGoogleMaps(plan.deepLinkUrl);
    } catch {
      setError("Could not open Google Maps.");
    }
  }

  // Development only. Replays the planned route through the same handler
  // the GPS task calls, so warnings, drift and the re-plan prompt all run
  // without leaving the desk. Stripped from release builds.
  async function endTrip() {
    await stopTrip();
    setWatching(false);
    setTick(null);
  }

  async function enableWarnings() {
    const granted = await requestDrivePermissions();
    setCanWarn(granted);
    if (!granted) {
      setError("Warnings need location access set to Allow all the time.");
    }
  }

  async function simulate(veerMeters: number) {
    if (plan === null || simulating) {
      return;
    }
    const route = decodePolyline(plan.routePolyline);
    await startTrip(destination, route, plan.cameras.filter((c) => !c.avoided));
    setSimulating(true);
    setTick(null);
    simulateDrive({
      route,
      veerMeters,
      speedMps: 25,
      tickMs: 400,
      onTick: async (position, speedMps) => {
        const result = await handleLocation(position, speedMps);
        // Announcements and prompts are worth keeping on screen; a plain
        // tick only updates the distance readout.
        setTick((previous) =>
          result.spoke || result.prompted || result.arrived
            ? result
            : { ...result, spoke: previous?.spoke, prompted: previous?.prompted }
        );
      },
      onFinish: () => setSimulating(false),
    });
  }

  if (plan === null) {
    return (
      <View className="flex-1 items-center justify-center bg-white">
        <ActivityIndicator />
        <Text className="mt-4 text-gray-500">Planning around cameras</Text>
      </View>
    );
  }

  const unavoidable = plan.cameras.filter((camera) => !camera.avoided);

  return (
    <View className="flex-1 bg-white">
      <ScrollView className="flex-1 px-4 pt-4">
        <View className="items-center rounded-lg border border-gray-200 py-8">
          <Text className="text-6xl font-bold text-gray-900">{plan.avoidedCount}</Text>
          <Text className="mt-1 text-gray-600">
            {plan.avoidedCount === 1 ? "camera avoided" : "cameras avoided"}
          </Text>
        </View>

        <View className="mt-4 rounded-lg border border-gray-200 p-4">
          <Text className="text-base text-gray-900">
            {minutes(plan.routeEtaSeconds)} min, {formatDelta(plan.etaDeltaSeconds)} the
            fastest route
          </Text>
          <Text className="mt-1 text-gray-600">{destination.name}</Text>
        </View>

        <Text className="mb-1 mt-6 text-gray-600">
          {unavoidable.length === 0
            ? "No cameras on this route."
            : `${unavoidable.length} ${
                unavoidable.length === 1 ? "camera" : "cameras"
              } could not be avoided.${
                canWarn ? " You will get an audio alert near each one." : ""
              }`}
        </Text>

        {unavoidable.length > 0 && !canWarn ? (
          <View className="mt-3 rounded-lg border border-gray-200 p-4">
            <Text className="text-gray-900">Turn on camera warnings</Text>
            <Text className="mt-1 text-gray-600">
              To speak a warning as you approach these cameras, the app needs
              location access set to Allow all the time. Google Maps will be
              in front while you drive, so nothing less will do.
            </Text>
            <View className="mt-3">
              <Button mode="outlined" onPress={enableWarnings}>
                Enable warnings
              </Button>
            </View>
          </View>
        ) : null}

        {unavoidable.map((camera) => (
          <View key={camera.id}>
            <Divider />
            <List.Item
              title={cameraLabel(camera)}
              description={describeCamera(camera, plan)}
              left={(props) => <List.Icon {...props} icon="cctv" />}
            />
          </View>
        ))}
      </ScrollView>

      <View className="px-4 pt-2" style={{ paddingBottom: insets.bottom + 48 }}>
        <Button mode="contained" icon="navigation" onPress={startNavigation}>
          {watching ? "Back to Google Maps" : "Start in Google Maps"}
        </Button>
        {watching ? (
          <View className="mt-2">
            <Button mode="outlined" icon="stop" onPress={endTrip}>
              Stop watching
            </Button>
          </View>
        ) : null}
        {__DEV__ && tick !== null ? (
          <View className="mt-2 rounded border border-gray-200 p-2">
            <Text className="text-xs text-gray-600">
              {tick.arrived
                ? "Arrived, trip ended"
                : `${Math.round(tick.offRouteMeters)} m off route`}
            </Text>
            {tick.spoke ? (
              <Text className="mt-1 text-xs text-gray-900">spoke: {tick.spoke}</Text>
            ) : null}
            {tick.prompted ? (
              <Text className="mt-1 text-xs text-gray-900">re-plan prompt sent</Text>
            ) : null}
          </View>
        ) : null}
        {__DEV__ ? (
          <View className="mt-2 flex-row">
            <View className="flex-1">
              <Button mode="outlined" disabled={simulating} onPress={() => simulate(0)}>
                {simulating ? "Simulating" : "Simulate drive"}
              </Button>
            </View>
            <View className="w-2" />
            <View className="flex-1">
              <Button mode="outlined" disabled={simulating} onPress={() => simulate(300)}>
                Simulate wrong turn
              </Button>
            </View>
          </View>
        ) : null}
      </View>

      <Snackbar visible={error !== ""} onDismiss={() => setError("")}>
        {error}
      </Snackbar>
    </View>
  );
}

function minutes(seconds: number): number {
  return Math.round(seconds / 60);
}

// The delta is the number the user is being asked to accept, so a detour
// that costs under a minute says so rather than rounding to "0 min slower".
function formatDelta(seconds: number): string {
  if (seconds <= 0) {
    return "no slower than";
  }
  if (seconds < 60) {
    return "under a minute slower than";
  }
  return `${minutes(seconds)} min slower than`;
}

// How far into the trip the driver meets this camera. A latitude and
// longitude tells them nothing they can use from behind a wheel.
function describeCamera(camera: Camera, plan: Plan): string {
  const route = decodePolyline(plan.routePolyline);
  let travelled = 0;
  let best = { distance: Infinity, along: 0 };
  for (let i = 0; i < route.length - 1; i++) {
    const step = haversineMeters(route[i], route[i + 1]);
    const distance = haversineMeters(route[i], { lat: camera.lat, lng: camera.lng });
    if (distance < best.distance) best = { distance, along: travelled };
    travelled += step;
  }
  const km = best.along / 1000;
  return km < 1 ? "Near the start of the route" : `About ${km.toFixed(1)} km in`;
}

function cameraLabel(camera: Camera): string {
  return camera.type === "alpr" ? "License plate reader" : "Speed camera";
}
