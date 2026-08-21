import { Linking } from "react-native";

/**
 * Hands the planned route to Google Maps, which does the turn-by-turn
 * navigation (including Android Auto). The URL comes from the backend.
 *
 * Deliberately no canOpenURL check first. Since Android 11 that returns
 * false unless the app declares in its manifest which other apps it may
 * ask about, so the check failed on a real build while opening the link
 * would have worked perfectly well. Expo Go hid this, because it declares
 * a broad set of those queries itself.
 *
 * openURL reports its own failure, and the link is an ordinary https URL,
 * so the worst case is a browser opening Google Maps on the web rather
 * than nothing happening at all.
 */
export async function openInGoogleMaps(deepLinkUrl: string): Promise<void> {
  await Linking.openURL(deepLinkUrl);
}
