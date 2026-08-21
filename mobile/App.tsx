import "./global.css";

import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StatusBar } from "expo-status-bar";
import { PaperProvider } from "react-native-paper";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { Place } from "./src/api/types";
import PlanScreen from "./src/screens/PlanScreen";
import SearchScreen from "./src/screens/SearchScreen";

export type RootStackParamList = {
  Search: undefined;
  Plan: { origin: Place; destination: Place };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function App() {
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
