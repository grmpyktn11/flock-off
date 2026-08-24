// Shown once, before the first trip.
//
// Two things a driver has to hear before they trust a clean route: the
// camera data is community-sourced and will be incomplete, and this app
// is not the one doing the driving. Saying it once and plainly is worth
// more than a paragraph of terms nobody reads, and Play expects
// something like it for anything used behind the wheel.

import { ScrollView, View } from "react-native";
import { Button, Dialog, Portal, Text } from "react-native-paper";

type Props = {
  visible: boolean;
  onAccept: () => void;
};

export default function DrivingNotice({ visible, onAccept }: Props) {
  return (
    <Portal>
      {/* Not dismissable: the whole point is that it was read once. */}
      <Dialog visible={visible} dismissable={false}>
        <Dialog.Title>Before you drive</Dialog.Title>
        <Dialog.ScrollArea>
          <ScrollView contentContainerStyle={{ paddingVertical: 12 }}>
            <View style={{ gap: 14 }}>
              <Text variant="bodyMedium">
                Camera locations come from OpenStreetMap, which anyone can edit.
                They will sometimes be missing, out of date, or wrong. A route
                with no cameras on it is our best guess, not a guarantee.
              </Text>
              <Text variant="bodyMedium">
                Google Maps does the navigating. Watch the road and the signs,
                not this app, and obey traffic law and speed limits regardless
                of what any route suggests.
              </Text>
              <Text variant="bodyMedium">
                Warnings are spoken aloud while you drive. Set your volume
                before you set off.
              </Text>
            </View>
          </ScrollView>
        </Dialog.ScrollArea>
        <Dialog.Actions>
          <Button mode="contained" onPress={onAccept}>
            Got it
          </Button>
        </Dialog.Actions>
      </Dialog>
    </Portal>
  );
}
