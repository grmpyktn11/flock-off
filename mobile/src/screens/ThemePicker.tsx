// Shown once, before anything else: how do you want this to look?
//
// No copy beyond the choice itself. Each card is drawn in the theme it
// offers, which beats any description of it.

import { useEffect, useState } from "react";
import { Platform, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ThemeName } from "../theme/themes";

const MONO = Platform.select({ ios: "Menlo", default: "monospace" });

type Props = {
  onChoose: (name: ThemeName) => void;
};

export default function ThemePicker({ onChoose }: Props) {
  const insets = useSafeAreaInsets();
  const [cursor, setCursor] = useState(true);

  // The terminal's blinking cursor, on the card that offers the terminal.
  useEffect(() => {
    const timer = setInterval(() => setCursor((on) => !on), 530);
    return () => clearInterval(timer);
  }, []);

  return (
    <View
      className="flex-1 justify-center px-6"
      style={{
        backgroundColor: "#000000",
        paddingTop: insets.top,
        paddingBottom: insets.bottom,
      }}
    >
      <Pressable
        onPress={() => onChoose("standard")}
        className="rounded-2xl px-5 py-8"
        style={{ backgroundColor: "#FFFFFF" }}
        android_ripple={{ color: "#E5E7EB" }}
      >
        <Text className="text-xl font-bold" style={{ color: "#111827" }}>
          Standard
        </Text>
      </Pressable>

      <View className="h-4" />

      <Pressable
        onPress={() => onChoose("ghost")}
        className="px-5 py-8"
        style={{
          backgroundColor: "#000000",
          borderWidth: 1,
          borderColor: "#00A82D",
        }}
        android_ripple={{ color: "#00330F" }}
      >
        <Text
          className="text-xl font-bold"
          style={{ color: "#00FF41", fontFamily: MONO }}
        >
          {"> GHOST_MODE" + (cursor ? "\u2588" : " ")}
        </Text>
      </Pressable>
    </View>
  );
}
