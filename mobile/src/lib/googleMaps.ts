import { Linking } from "react-native";

// Hands the planned route to Google Maps, which does the turn-by-turn
// navigation (including Android Auto). The URL comes from the backend.
export async function openInGoogleMaps(deepLinkUrl: string): Promise<void> {
  const canOpen = await Linking.canOpenURL(deepLinkUrl);
  if (!canOpen) {
    throw new Error("Google Maps could not be opened on this device.");
  }
  await Linking.openURL(deepLinkUrl);
}
