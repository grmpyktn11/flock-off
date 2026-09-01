import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { ActivityIndicator, Button, List, Snackbar } from "react-native-paper";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { RootStackParamList } from "../../App";
import { ApiError, Camera, Plan, cameraExplanations, planRoute } from "../api";
import AiKeyDialog from "../components/AiKeyDialog";
import { cameraLabel, describeCamera, factorLines } from "../lib/cameraCopy";
import { openInGoogleMaps } from "../lib/googleMaps";
import { decodePolyline } from "../lib/polyline";
import { useAppTheme } from "../theme";
import { startTrip } from "../lib/tripStore";
import {
  canWatchDrive,
  reconcileTrip,
  requestDrivePermissions,
  startTripService,
  stopTrip,
} from "../lib/tripService";

type Props = NativeStackScreenProps<RootStackParamList, "Plan">;

export default function PlanScreen({ route }: Props) {
  const { origin, destination } = route.params;
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState("");
  // Bumped by the retry button when planning itself failed.
  const [attempt, setAttempt] = useState(0);
  // The camera whose "why is it here" line is expanded inline, and the
  // answers already fetched this visit, so re-tapping a camera is instant.
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [explanations, setExplanations] = useState<Record<number, string>>({});
  const [explainError, setExplainError] = useState("");
  // Set when the backend answered 402: the free AI notes are spent and
  // new ones need the user's own key. Remembers which camera asked, so
  // saving a key in the dialog can retry that exact request.
  const [needsKeyFor, setNeedsKeyFor] = useState<Camera | null>(null);
  const [keyDialogOpen, setKeyDialogOpen] = useState(false);
  const [canWarn, setCanWarn] = useState(true);
  const [watching, setWatching] = useState(false);
  const insets = useSafeAreaInsets();
  const { tokens } = useAppTheme();
  const body = { color: tokens.text, fontFamily: tokens.fontFamily };
  const muted = { color: tokens.textMuted, fontFamily: tokens.fontFamily };
  const card = {
    borderColor: tokens.border,
    backgroundColor: tokens.surface,
  };

  useEffect(() => {
    canWatchDrive().then(setCanWarn);
    // A trip survives the app being closed, so coming back here has to
    // reflect whether one is genuinely still running - not merely whether
    // one is on disk, which it can be long after the service has gone.
    reconcileTrip().then(setWatching);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setError("");
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
  }, [origin, destination, attempt]);

  async function startNavigation() {
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

  async function endTrip() {
    await stopTrip();
    setWatching(false);
  }

  // Expand the tapped camera's "why is it here" line, fetching the answer
  // the first time. Answers the backend already has cached come back
  // fast; a brand new one costs a short Claude call.
  function toggleWhy(camera: Camera) {
    if (expandedId === camera.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(camera.id);
    if (explanations[camera.id] === undefined) {
      fetchWhy(camera);
    }
  }

  function fetchWhy(camera: Camera) {
    setExplainError("");
    setNeedsKeyFor(null);
    cameraExplanations([camera.id])
      .then((result) => {
        setExplanations((previous) => ({ ...previous, ...result }));
        if (result[camera.id] === undefined) {
          setExplainError("No explanation available for this camera.");
        }
      })
      .catch((cause) => {
        setExplainError(
          cause instanceof ApiError
            ? cause.message
            : "Could not load the explanation."
        );
        if (cause instanceof ApiError && cause.status === 402) {
          setNeedsKeyFor(camera);
        }
      });
  }

  async function enableWarnings() {
    const granted = await requestDrivePermissions();
    setCanWarn(granted);
    if (!granted) {
      setError("Alerts need location access set to Allow all the time.");
    }
  }

  if (plan === null) {
    // A failed plan used to leave this spinner up forever: the error
    // snackbar only rendered on the planned screen, which a failure never
    // reaches. Failure gets its own words and a way to try again.
    return (
      <View
        className="flex-1 items-center justify-center px-8"
        style={{ backgroundColor: tokens.background }}
      >
        {error === "" ? (
          <>
            <ActivityIndicator />
            <Text className="mt-4" style={muted}>
              Looking up public camera data…
            </Text>
          </>
        ) : (
          <>
            <Text className="text-center" style={body}>
              {error}
            </Text>
            <View className="mt-4">
              <Button mode="outlined" onPress={() => setAttempt(attempt + 1)}>
                Try again
              </Button>
            </View>
          </>
        )}
      </View>
    );
  }

  const unavoidable = plan.cameras.filter((camera) => !camera.avoided);
  // Plate readers are the app's subject; speed cameras ride along in a
  // collapsed group since they only matter at speed.
  const readers = plan.cameras.filter((camera) => camera.type === "alpr");
  const readersOnPath = readers.filter((camera) => !camera.avoided);
  const readersAvoided = readers.filter((camera) => camera.avoided);
  const speedCams = plan.cameras.filter(
    (camera) => camera.type === "speed_camera"
  );

  function cameraRow(camera: Camera) {
    const expanded = expandedId === camera.id;
    // The site's camera list, carried over: a raspberry rail for a camera
    // on the path, olive for one the detour goes around.
    const rail = camera.avoided ? tokens.olive : tokens.accent;
    return (
      <View
        key={camera.id}
        className="mb-2 overflow-hidden rounded-r-xl"
        style={{ backgroundColor: tokens.surface, borderLeftWidth: 3, borderLeftColor: rail }}
      >
        <List.Item
          title={cameraLabel(camera)}
          description={describeCamera(camera, plan!)}
          descriptionNumberOfLines={3}
          left={(props) => (
            <List.Icon
              {...props}
              color={rail}
              icon={
                camera.type === "speed_camera"
                  ? "speedometer"
                  : camera.avoided
                    ? "cctv-off"
                    : "cctv"
              }
            />
          )}
          right={(props) => (
            <List.Icon {...props} icon={expanded ? "chevron-up" : "chevron-down"} />
          )}
          onPress={() => toggleWhy(camera)}
        />
        {expanded ? (
          <View
            className="mb-3 ml-4 mr-4 pl-3"
            style={{ borderLeftWidth: 3, borderLeftColor: tokens.olive }}
          >
            <Text
              style={{
                color:
                  camera.usefulnessScore !== null &&
                  camera.usefulnessScore < 30
                    ? tokens.accent
                    : tokens.text,
                fontFamily: tokens.fontFamilySemibold,
              }}
            >
              {camera.usefulnessScore !== null
                ? `Useful score: ${camera.usefulnessScore}/100`
                : "Useful score: not enough public data"}
            </Text>
            {camera.scoreDesc ? (
              <Text className="text-xs" style={muted}>
                {camera.scoreDesc}
              </Text>
            ) : null}
            {factorLines(camera).map((line) => (
              <Text key={line} className="mt-1" style={body}>
                {`• ${line}`}
              </Text>
            ))}
            <View className="mt-2">
              {explanations[camera.id] !== undefined ? (
                <Text className="text-xs" style={muted}>
                  {explanations[camera.id]}
                </Text>
              ) : explainError !== "" ? (
                <View>
                  <Text className="text-xs" style={muted}>
                    {explainError}
                  </Text>
                  <View className="flex-row items-center">
                    {needsKeyFor !== null ? (
                      <Button
                        compact
                        mode="text"
                        onPress={() => setKeyDialogOpen(true)}
                      >
                        Add API key
                      </Button>
                    ) : null}
                    <Button compact mode="text" onPress={() => fetchWhy(camera)}>
                      Retry
                    </Button>
                  </View>
                </View>
              ) : (
                <View className="flex-row items-center">
                  <ActivityIndicator size="small" />
                  <Text className="ml-2 text-xs" style={muted}>
                    Reading the numbers…
                  </Text>
                </View>
              )}
            </View>
          </View>
        ) : null}
      </View>
    );
  }

  return (
    <View className="flex-1" style={{ backgroundColor: tokens.background }}>
      <ScrollView className="flex-1 px-4 pt-4">
        <View
          className="rounded-3xl border p-6"
          style={{
            ...card,
            shadowColor: "#533F16",
            shadowOpacity: 0.12,
            shadowRadius: 18,
            shadowOffset: { width: 0, height: 10 },
            elevation: 2,
          }}
        >
          {/* The number is the verdict; everything else supports it. */}
          <Text
            style={{
              fontFamily: tokens.fontFamilyBold,
              fontSize: 56,
              lineHeight: 60,
              letterSpacing: -2,
              color: readers.length === 0 ? tokens.oliveDeep : tokens.accent,
            }}
          >
            {readers.length}
          </Text>
          <Text
            className="text-lg"
            style={{ color: tokens.text, fontFamily: tokens.fontFamilySemibold }}
          >
            {`license plate ${
              readers.length === 1 ? "reader" : "readers"
            } on the way to ${destination.name}`}
          </Text>
          <Text className="mt-1" style={muted}>
            {`${minutes(plan.baselineEtaSeconds)} min drive`}
            {speedCams.length > 0
              ? ` · ${speedCams.length} speed ${
                  speedCams.length === 1 ? "camera" : "cameras"
                }`
              : ""}
          </Text>
          {readersAvoided.length > 0 ? (
            <Text className="mt-3" style={body}>
              Avoiding {readersAvoided.length} of the readers would take{" "}
              <Text
                style={{
                  color: tokens.oliveDeep,
                  fontFamily: tokens.fontFamilySemibold,
                }}
              >
                {formatCost(plan.etaDeltaSeconds)}
                {percentSlower(plan.etaDeltaSeconds, plan.baselineEtaSeconds)}
              </Text>
              .
            </Text>
          ) : readers.length > 0 ? (
            <Text className="mt-2" style={muted}>
              None of the readers can be routed around on this trip.
            </Text>
          ) : null}
          <View className="mt-4">
            <Button mode="contained" icon="navigation" onPress={startNavigation}>
              {watching ? "Back to Google Maps" : "See potential path"}
            </Button>
          </View>
        </View>

        {readersOnPath.length > 0 ? (
          <View className="mb-2 mt-6">
            <Text
              className="text-xs uppercase tracking-wide"
              style={{ color: tokens.accent, fontFamily: tokens.fontFamilyBold }}
            >
              {`On the path — ${readersOnPath.length}`}
            </Text>
            <Text className="mt-1" style={muted}>
              These stay either way. Tap one to see why it is there.
            </Text>
          </View>
        ) : null}
        {readersOnPath.map(cameraRow)}

        {readersAvoided.length > 0 ? (
          <View className="mb-2 mt-6">
            <Text
              className="text-xs uppercase tracking-wide"
              style={{ color: tokens.oliveDeep, fontFamily: tokens.fontFamilyBold }}
            >
              {`Routed around — ${readersAvoided.length}`}
            </Text>
          </View>
        ) : null}
        {readersAvoided.map(cameraRow)}

        {speedCams.length > 0 ? (
          <View
            className="mt-6 overflow-hidden rounded-2xl border"
            style={{ borderColor: tokens.border }}
          >
            <List.Accordion
              title={`Speed cameras (${speedCams.length})`}
              style={{ backgroundColor: tokens.background }}
              left={(props) => <List.Icon {...props} icon="speedometer" />}
            >
              {speedCams.map(cameraRow)}
            </List.Accordion>
          </View>
        ) : null}
      </ScrollView>

      <View className="px-4 pt-2" style={{ paddingBottom: insets.bottom + 48 }}>
        {unavoidable.length > 0 && !canWarn ? (
          <Button mode="outlined" icon="bell-outline" onPress={enableWarnings}>
            Turn on heads-up alerts
          </Button>
        ) : null}
        {watching ? (
          <View className="mt-2">
            <Button mode="outlined" icon="stop" onPress={endTrip}>
              Stop watching
            </Button>
          </View>
        ) : null}
      </View>

      <Snackbar visible={error !== ""} onDismiss={() => setError("")}>
        {error}
      </Snackbar>

      <AiKeyDialog
        visible={keyDialogOpen}
        onDismiss={(saved) => {
          setKeyDialogOpen(false);
          // A newly saved key should immediately answer the question that
          // surfaced the dialog, not leave the user to find Retry.
          if (saved && needsKeyFor !== null) {
            fetchWhy(needsKeyFor);
          }
        }}
      />
    </View>
  );
}

function minutes(seconds: number): number {
  return Math.round(seconds / 60);
}

// The delta is the number the user is being asked to accept, so a detour
// that costs under a minute says so rather than rounding to "0 min".
function formatCost(seconds: number): string {
  if (seconds <= 0) {
    return "no extra time";
  }
  if (seconds < 60) {
    return "under a minute longer";
  }
  return `${minutes(seconds)} min longer`;
}

// " — a 18% longer trip", or nothing when the increase rounds to zero.
function percentSlower(deltaSeconds: number, baselineSeconds: number): string {
  if (deltaSeconds <= 0 || baselineSeconds <= 0) {
    return "";
  }
  const percent = Math.round((deltaSeconds / baselineSeconds) * 100);
  return percent >= 1 ? ` — a ${percent}% longer trip` : "";
}
