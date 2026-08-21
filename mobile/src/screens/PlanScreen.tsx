import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { ActivityIndicator, Button, Divider, List, Snackbar } from "react-native-paper";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { RootStackParamList } from "../../App";
import { ApiError, Camera, Plan, planRoute } from "../api";
import { openInGoogleMaps } from "../lib/googleMaps";

type Props = NativeStackScreenProps<RootStackParamList, "Plan">;

export default function PlanScreen({ route }: Props) {
  const { origin, destination } = route.params;
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState("");
  const insets = useSafeAreaInsets();

  useEffect(() => {
    let cancelled = false;
    planRoute(origin, destination)
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
  }, [origin, destination]);

  async function startNavigation() {
    if (plan === null) {
      return;
    }
    try {
      await openInGoogleMaps(plan.deepLinkUrl);
    } catch {
      setError("Could not open Google Maps.");
    }
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
          <Text className="mt-1 text-gray-600">cameras avoided</Text>
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
            : `${unavoidable.length} camera(s) could not be avoided. You will get an audio alert near each one.`}
        </Text>

        {unavoidable.map((camera) => (
          <View key={camera.id}>
            <Divider />
            <List.Item
              title={cameraLabel(camera)}
              description={`${camera.lat.toFixed(4)}, ${camera.lng.toFixed(4)}`}
              left={(props) => <List.Icon {...props} icon="cctv" />}
            />
          </View>
        ))}
      </ScrollView>

      <View className="px-4 pt-2" style={{ paddingBottom: insets.bottom + 48 }}>
        <Button mode="contained" icon="navigation" onPress={startNavigation}>
          Start in Google Maps
        </Button>
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

function cameraLabel(camera: Camera): string {
  return camera.type === "alpr" ? "License plate reader" : "Speed camera";
}
