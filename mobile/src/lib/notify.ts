// The off-route prompt.
//
// It has to be a notification, not a dialog. Google Maps is the app in
// front while driving, and Android does not let a backgrounded app draw
// over it. A high-priority notification with an action is the most
// direct thing available.

import * as Notifications from "expo-notifications";

export const REPLAN_CATEGORY = "replan";
export const REPLAN_ACTION = "replan-accept";

export async function configureNotifications(): Promise<void> {
  try {
    await Notifications.requestPermissionsAsync();
    await Notifications.setNotificationCategoryAsync(REPLAN_CATEGORY, [
      {
        identifier: REPLAN_ACTION,
        buttonTitle: "Re-plan",
        options: { opensAppToForeground: true },
      },
    ]);
  } catch {
    // Expo Go's notification support is limited. Losing the category
    // costs the action button, not the app.
  }
}

// Without this a notification raised while the app is in the foreground
// is swallowed, which is exactly the case the simulator exercises.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export async function promptToReplan(avoidedCount: number): Promise<void> {
  try {
    const cameras = avoidedCount === 1 ? "1 camera" : `${avoidedCount} cameras`;
    await Notifications.scheduleNotificationAsync({
      content: {
        title: "Off the planned route",
        body: `A new route from here would avoid ${cameras}.`,
        categoryIdentifier: REPLAN_CATEGORY,
        // The driver is looking at the road, so this has to arrive as a
        // heads-up banner with sound rather than sit in the shade.
        priority: Notifications.AndroidNotificationPriority.HIGH,
        sound: true,
      },
      trigger: null,
    });
  } catch {
    // Same again: no notification is better than a crash mid-drive.
  }
}
