import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useEffect, useRef, useState } from "react";
import { FlatList, Text, View } from "react-native";
import {
  ActivityIndicator,
  Button,
  Divider,
  IconButton,
  List,
  TextInput,
} from "react-native-paper";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { RootStackParamList } from "../../App";
import AiKeyDialog from "../components/AiKeyDialog";
import { useAppTheme } from "../theme";
import { Place, PlaceSuggestion, placeDetails, searchPlaces } from "../api";
import { newSessionToken } from "../lib/session";

type Props = NativeStackScreenProps<RootStackParamList, "Search">;

type Field = "origin" | "destination";

export default function SearchScreen({ navigation }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  const [originQuery, setOriginQuery] = useState("");
  const [destinationQuery, setDestinationQuery] = useState("");
  const [activeField, setActiveField] = useState<Field>("origin");
  const [results, setResults] = useState<PlaceSuggestion[]>([]);
  const [searching, setSearching] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  // One Google billing session per search burst, closed by the details
  // call when a place is picked.
  const sessionToken = useRef(newSessionToken());
  const insets = useSafeAreaInsets();
  const { tokens } = useAppTheme();
  // Paper components take their colors from the provider; these styles
  // cover the plain RN pieces the provider cannot reach.
  const body = { color: tokens.text, fontFamily: tokens.fontFamily };
  const muted = { color: tokens.textMuted, fontFamily: tokens.fontFamily };

  const query = activeField === "origin" ? originQuery : destinationQuery;
  const selected = activeField === "origin" ? origin : destination;

  // The app's one setting - the user's own AI key - lives behind a gear
  // here rather than a whole settings screen it would rattle around in.
  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <IconButton
          icon="cog-outline"
          accessibilityLabel="AI settings"
          onPress={() => setSettingsOpen(true)}
        />
      ),
    });
  }, [navigation]);

  useEffect(() => {
    // Nothing to look up when the field already holds a chosen place.
    if (selected !== null && selected.name === query) {
      setResults([]);
      setSearching(false);
      return;
    }

    // Debounce so a burst of keystrokes is one call to the search proxy.
    let cancelled = false;
    setSearching(query.trim().length > 0);
    const timer = setTimeout(() => {
      searchPlaces(query, undefined, sessionToken.current)
        .then((places) => {
          if (!cancelled) {
            setResults(places);
            setSearching(false);
          }
        })
        .catch(() => {
          // A failed lookup should not wedge the spinner on. The user can
          // keep typing, and the next keystroke tries again.
          if (!cancelled) {
            setResults([]);
            setSearching(false);
          }
        });
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, selected]);

  async function selectPlace(suggestion: PlaceSuggestion) {
    // Autocomplete gives no coordinates, so the chosen one is resolved
    // now. Reusing the search's token closes the billing session; the
    // next search starts a fresh one.
    setResults([]);
    setResolving(true);
    try {
      const place = await placeDetails(suggestion.placeId, sessionToken.current);
      sessionToken.current = newSessionToken();
      if (activeField === "origin") {
        setOrigin(place);
        setOriginQuery(place.name);
      } else {
        setDestination(place);
        setDestinationQuery(place.name);
      }
    } catch {
      // Leave the field as the driver typed it so they can pick again.
      setResults([suggestion]);
    } finally {
      setResolving(false);
    }
  }

  function editField(field: Field, text: string) {
    if (field === "origin") {
      setOrigin(null);
      setOriginQuery(text);
    } else {
      setDestination(null);
      setDestinationQuery(text);
    }
  }

  const canPlan = origin !== null && destination !== null;

  return (
    <View className="flex-1 px-4 pt-4" style={{ backgroundColor: tokens.background }}>
      <TextInput
        label="Start"
        mode="outlined"
        value={originQuery}
        onFocus={() => setActiveField("origin")}
        onChangeText={(text) => editField("origin", text)}
      />
      <View className="h-3" />
      <TextInput
        label="Destination"
        mode="outlined"
        value={destinationQuery}
        onFocus={() => setActiveField("destination")}
        onChangeText={(text) => editField("destination", text)}
      />

      <View className="mt-4 flex-1">
        {searching || resolving ? (
          <View className="mt-6">
            <ActivityIndicator />
          </View>
        ) : (
          <FlatList
            data={results}
            keyExtractor={(place) => place.placeId}
            keyboardShouldPersistTaps="handled"
            ItemSeparatorComponent={Divider}
            renderItem={({ item }) => (
              <List.Item
                title={item.name}
                description={item.address}
                left={(props) => <List.Icon {...props} icon="map-marker-outline" />}
                onPress={() => selectPlace(item)}
              />
            )}
            ListEmptyComponent={
              <Text className="mt-6 text-center" style={muted}>
                {canPlan
                  ? "Both places set. Plan the route below."
                  : `Search for a place to fill the ${
                      activeField === "origin" ? "start" : "destination"
                    } field.`}
              </Text>
            }
          />
        )}
      </View>

      <View className="pt-2" style={{ paddingBottom: insets.bottom + 48 }}>
        <Button
          mode="contained"
          disabled={!canPlan}
          onPress={() => {
            if (origin !== null && destination !== null) {
              navigation.navigate("Plan", { origin, destination });
            }
          }}
        >
          Plan route
        </Button>
      </View>

      <AiKeyDialog visible={settingsOpen} onDismiss={() => setSettingsOpen(false)} />
    </View>
  );
}
