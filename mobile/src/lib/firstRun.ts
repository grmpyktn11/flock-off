// Whether the driving notice has been shown, on disk.
//
// A version number rather than a boolean, so a materially changed notice
// can be shown again to people who already accepted the old one. Bumping
// it re-prompts everyone; leaving it alone never does.

import AsyncStorage from "@react-native-async-storage/async-storage";

const KEY = "acceptedNoticeVersion";

export const NOTICE_VERSION = 1;

export async function hasAcceptedNotice(): Promise<boolean> {
  try {
    const stored = await AsyncStorage.getItem(KEY);
    return stored !== null && Number(stored) >= NOTICE_VERSION;
  } catch {
    // Storage failing is not a reason to block someone from driving. Show
    // the notice again instead - the cost of that is one extra tap.
    return false;
  }
}

export async function acceptNotice(): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, String(NOTICE_VERSION));
  } catch {
    // Same reasoning: they will see it once more next launch.
  }
}
