import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useEffect, useState } from "react";
import { FlatList, Text, View } from "react-native";
import { ActivityIndicator, Button, Divider, List, TextInput } from "react-native-paper";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { RootStackParamList } from "../../App";
import { searchPlaces } from "../api/mockBackend";
import { Place } from "../api/types";

type Props = NativeStackScreenProps<RootStackParamList, "Search">;

type Field = "origin" | "destination";

export default function SearchScreen({ navigation }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  const [originQuery, setOriginQuery] = useState("");
  const [destinationQuery, setDestinationQuery] = useState("");
  const [activeField, setActiveField] = useState<Field>("origin");
  const [results, setResults] = useState<Place[]>([]);
  const [searching, setSearching] = useState(false);
  const insets = useSafeAreaInsets();

  const query = activeField === "origin" ? originQuery : destinationQuery;
  const selected = activeField === "origin" ? origin : destination;

  useEffect(() => {
    // Nothing to look up when the field already holds a chosen place.
    if (selected !== null && selected.description === query) {
      setResults([]);
      setSearching(false);
      return;
    }

    // Debounce so a burst of keystrokes is one call to the search proxy.
    let cancelled = false;
    setSearching(query.trim().length > 0);
    const timer = setTimeout(() => {
      searchPlaces(query).then((places) => {
        if (!cancelled) {
          setResults(places);
          setSearching(false);
        }
      });
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, selected]);

  function selectPlace(place: Place) {
    if (activeField === "origin") {
      setOrigin(place);
      setOriginQuery(place.description);
    } else {
      setDestination(place);
      setDestinationQuery(place.description);
    }
    setResults([]);
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
    <View className="flex-1 bg-white px-4 pt-4">
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
        {searching ? (
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
                title={item.description}
                left={(props) => <List.Icon {...props} icon="map-marker-outline" />}
                onPress={() => selectPlace(item)}
              />
            )}
            ListEmptyComponent={
              <Text className="mt-6 text-center text-gray-500">
                Search for a place to fill the{" "}
                {activeField === "origin" ? "start" : "destination"} field.
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
    </View>
  );
}
