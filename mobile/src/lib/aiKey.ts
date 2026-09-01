// The user's own Anthropic key, and this device's identity for the
// free-explanation allowance.
//
// New explanations are written by Claude and someone has to pay for the
// call: the backend covers each install's first few, counted by install
// id, and after that it asks for the user's own key. The key lives only
// on this phone and travels only to our backend, which uses it for the
// one batch and never stores it.

import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Application from "expo-application";
import * as Crypto from "expo-crypto";

const KEY = "anthropicApiKey";
const INSTALL_ID = "installId";

export async function getAnthropicKey(): Promise<string> {
  try {
    return (await AsyncStorage.getItem(KEY)) ?? "";
  } catch {
    // No storage means no key, which the backend treats as "use the
    // free allowance" - the feature degrades, nothing breaks.
    return "";
  }
}

export async function setAnthropicKey(value: string): Promise<void> {
  try {
    const trimmed = value.trim();
    if (trimmed === "") {
      await AsyncStorage.removeItem(KEY);
    } else {
      await AsyncStorage.setItem(KEY, trimmed);
    }
  } catch {
    // Saving failed; the next explanation request simply won't carry it.
  }
}

/**
 * A stable id for counting the free explanation batches, derived from
 * ANDROID_ID so uninstalling and reinstalling does not mint a fresh
 * allowance - it survives reinstalls and resets only with a factory
 * reset. Two privacy properties keep this honest: ANDROID_ID is scoped
 * to our signing key since Android 8, so it cannot cross-reference this
 * app's users with anyone else's, and it is hashed here with an
 * app-local salt so the device identifier itself never leaves the phone.
 * The backend sees an opaque token it could not reverse or share.
 */
export async function getInstallId(): Promise<string> {
  try {
    const androidId = Application.getAndroidId();
    if (androidId) {
      return await Crypto.digestStringAsync(
        Crypto.CryptoDigestAlgorithm.SHA256,
        `flock-off:${androidId}`
      );
    }
    // Not Android (or no id): fall back to a random id minted once and
    // kept in storage. It resets on reinstall, which is the best a
    // platform without a stable scoped id offers.
    const existing = await AsyncStorage.getItem(INSTALL_ID);
    if (existing !== null) {
      return existing;
    }
    const minted = Crypto.randomUUID();
    await AsyncStorage.setItem(INSTALL_ID, minted);
    return minted;
  } catch {
    // Without any id the backend cannot count, so it grants no free
    // batches rather than uncountably many - the honest fallback.
    return "";
  }
}
