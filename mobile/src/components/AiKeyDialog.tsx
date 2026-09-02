// The one settings surface in the app: the user's own Anthropic key.
//
// Reached from the gear on the search screen, and offered inline when
// the backend answers 402 - the moment the free explanations run out is
// the moment the field is wanted.

import { useEffect, useState } from "react";
import { Linking, Text } from "react-native";
import { Button, Dialog, Portal, TextInput } from "react-native-paper";

import { getAnthropicKey, setAnthropicKey } from "../lib/aiKey";
import { useAppTheme } from "../theme";

type Props = {
  visible: boolean;
  // Called on any close. saved is true when the key changed, so the
  // caller can retry the request that surfaced this dialog.
  onDismiss: (saved: boolean) => void;
};

export default function AiKeyDialog({ visible, onDismiss }: Props) {
  const [draft, setDraft] = useState("");
  const [hadKey, setHadKey] = useState(false);
  const { tokens } = useAppTheme();

  useEffect(() => {
    if (visible) {
      getAnthropicKey().then((key) => {
        setDraft(key);
        setHadKey(key !== "");
      });
    }
  }, [visible]);

  async function save() {
    await setAnthropicKey(draft);
    onDismiss(true);
  }

  return (
    <Portal>
      <Dialog
        visible={visible}
        onDismiss={() => onDismiss(false)}
        style={{ backgroundColor: tokens.surface }}
      >
        <Dialog.Title style={{ color: tokens.text, fontFamily: tokens.fontFamilySemibold }}>
          AI explanations
        </Dialog.Title>
        <Dialog.Content>
          <Text style={{ color: tokens.textMuted, fontFamily: tokens.fontFamily }}>
            The short "why is this camera here" notes are written by
            Claude. Your first few are on us; after that they run on your
            own Anthropic API key (from console.anthropic.com). The key
            stays on this phone and is only used to write new notes.
          </Text>
          <TextInput
            mode="outlined"
            label="Anthropic API key"
            placeholder="sk-ant-…"
            value={draft}
            onChangeText={setDraft}
            autoCapitalize="none"
            autoCorrect={false}
            style={{ marginTop: 12 }}
          />
          <Text
            accessibilityRole="link"
            onPress={() =>
              Linking.openURL(
                "https://github.com/grmpyktn11/flock-off/blob/main/docs/privacy.md"
              )
            }
            style={{
              color: tokens.textMuted,
              fontFamily: tokens.fontFamily,
              textDecorationLine: "underline",
              marginTop: 12,
            }}
          >
            Privacy policy
          </Text>
        </Dialog.Content>
        <Dialog.Actions>
          {hadKey && draft === "" ? (
            <Button onPress={save}>Remove key</Button>
          ) : null}
          <Button onPress={() => onDismiss(false)}>Cancel</Button>
          <Button mode="contained" onPress={save} disabled={draft.trim() === "" && !hadKey}>
            Save
          </Button>
        </Dialog.Actions>
      </Dialog>
    </Portal>
  );
}
