import "./global.css";

import {
  SpaceGrotesk_400Regular,
  SpaceGrotesk_600SemiBold,
  SpaceGrotesk_700Bold,
  useFonts,
} from "@expo-google-fonts/space-grotesk";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import * as Notifications from "expo-notifications";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { PaperProvider } from "react-native-paper";
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
import { ThemeProvider, useAppTheme } from "./src/theme";

export type RootStackParamList = {
  Search: undefined;
  Plan: { origin: Place; destination: Place };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

// The Search -> Plan flow.
function NavigateStack() {
  const { tokens } = useAppTheme();
  return (
    <Stack.Navigator
      screenOptions={{
        headerTitleStyle: { fontFamily: tokens.fontFamilySemibold },
        headerShadowVisible: false,
      }}
    >
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
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ThemedApp />
    </ThemeProvider>
  );
}

function ThemedApp() {
  const { tokens } = useAppTheme();
  // The whole look leans on the site's typeface, so hold the blank
  // launch screen the extra beat the fonts take rather than flashing
  // system type first.
  const [fontsLoaded] = useFonts({
    SpaceGrotesk_400Regular,
    SpaceGrotesk_600SemiBold,
    SpaceGrotesk_700Bold,
  });
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

  if (!fontsLoaded) {
    return null;
  }

  return (
    <SafeAreaProvider>
      <PaperProvider theme={tokens.paper}>
        <NavigationContainer theme={tokens.nav}>
          <NavigateStack />
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
