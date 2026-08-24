import "./global.css";

import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import * as Notifications from "expo-notifications";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { IconButton, PaperProvider } from "react-native-paper";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { Place } from "./src/api/types";
import { acceptNotice, hasAcceptedNotice } from "./src/lib/firstRun";
import { openInGoogleMaps } from "./src/lib/googleMaps";
import { REPLAN_ACTION, configureNotifications } from "./src/lib/notify";
import { loadTrip, save } from "./src/lib/tripStore";
// Imported for its side effect: the location task has to be defined
// before Android can deliver a location to it, including after the OS
// restarts the process.
import "./src/lib/tripService";
import DrivingNotice from "./src/screens/DrivingNotice";
import PlanScreen from "./src/screens/PlanScreen";
import SearchScreen from "./src/screens/SearchScreen";
import ThemePicker from "./src/screens/ThemePicker";
import { ThemeProvider, useAppTheme } from "./src/theme";

export type RootStackParamList = {
  Search: undefined;
  Plan: { origin: Place; destination: Place; strict: boolean };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function App() {
  return (
    <ThemeProvider>
      <ThemedApp />
    </ThemeProvider>
  );
}

function ThemedApp() {
  const { tokens, chosen, choose } = useAppTheme();
  // null until the answer comes back from disk, so the dialog does not
  // flash on screen for someone who accepted it months ago.
  const [noticeAccepted, setNoticeAccepted] = useState<boolean | null>(null);

  useEffect(() => {
    hasAcceptedNotice().then(setNoticeAccepted);
  }, []);

  useEffect(() => {
    configureNotifications();

    // Tapping "Re-plan" on the off-route notification. The re-plan that
    // decided to prompt already produced the link, so this just fires it.
    const subscription = Notifications.addNotificationResponseReceivedListener(
      async (response) => {
        if (response.actionIdentifier !== REPLAN_ACTION) return;
        const trip = await loadTrip();
        if (!trip?.pendingDeepLink) return;
        await save({ ...trip, pendingDeepLink: undefined });
        await openInGoogleMaps(trip.pendingDeepLink);
      }
    );
    return () => subscription.remove();
  }, []);

  // Theme first, notice second: the picker is the very first screen a
  // new install sees, and nothing else renders until it is answered.
  if (chosen === null) {
    return null;
  }
  if (chosen === false) {
    return (
      <SafeAreaProvider>
        <ThemePicker onChoose={choose} />
        <StatusBar style="light" />
      </SafeAreaProvider>
    );
  }

  const ghost = tokens.name === "ghost";

  return (
    <SafeAreaProvider>
      <PaperProvider theme={tokens.paper}>
        <NavigationContainer theme={tokens.nav}>
          <Stack.Navigator
            screenOptions={{
              headerTitleStyle: { fontFamily: tokens.fontFamily },
            }}
          >
            <Stack.Screen
              name="Search"
              component={SearchScreen}
              options={{
                title: ghost ? "> plan_route" : "Plan a route",
                // The picker promised "change your mind later"; this is
                // where that promise is kept.
                headerRight: () => (
                  <IconButton
                    icon="theme-light-dark"
                    onPress={() => choose(ghost ? "standard" : "ghost")}
                  />
                ),
              }}
            />
            <Stack.Screen
              name="Plan"
              component={PlanScreen}
              options={{ title: ghost ? "> route_plan" : "Route plan" }}
            />
          </Stack.Navigator>
        </NavigationContainer>
        <DrivingNotice
          visible={noticeAccepted === false}
          onAccept={() => {
            setNoticeAccepted(true);
            acceptNotice();
          }}
        />
        <StatusBar style={tokens.statusBar} />
      </PaperProvider>
    </SafeAreaProvider>
  );
}
