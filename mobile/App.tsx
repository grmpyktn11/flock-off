import "./global.css";

import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import * as Notifications from "expo-notifications";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { PaperProvider } from "react-native-paper";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { Place } from "./src/api/types";
import { openInGoogleMaps } from "./src/lib/googleMaps";
import { REPLAN_ACTION, configureNotifications } from "./src/lib/notify";
import { loadTrip, save } from "./src/lib/tripStore";
// Imported for its side effect: the location task has to be defined
// before Android can deliver a location to it, including after the OS
// restarts the process.
import "./src/lib/tripService";
import PlanScreen from "./src/screens/PlanScreen";
import SearchScreen from "./src/screens/SearchScreen";

export type RootStackParamList = {
  Search: undefined;
  Plan: { origin: Place; destination: Place; strict: boolean };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function App() {
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

  return (
    <SafeAreaProvider>
      <PaperProvider>
        <NavigationContainer>
          <Stack.Navigator>
            <Stack.Screen
              name="Search"
              component={SearchScreen}
              options={{ title: "Plan a route" }}
            />
            <Stack.Screen
              name="Plan"
              component={PlanScreen}
              options={{ title: "Route plan" }}
            />
          </Stack.Navigator>
        </NavigationContainer>
        <StatusBar style="auto" />
      </PaperProvider>
    </SafeAreaProvider>
  );
}
