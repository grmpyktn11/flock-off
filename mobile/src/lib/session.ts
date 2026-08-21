// Google bills autocomplete by session, not by request: a burst of
// keystrokes plus the Place Details call that resolves the chosen result
// count as one, as long as they share a token.
//
// So a token lives from the first keystroke until a place is picked, and
// a new one starts the next search.

export function newSessionToken(): string {
  // Google only requires that this be unique per session. Random hex is
  // enough and avoids pulling in a uuid dependency for one string.
  return (
    Math.random().toString(16).slice(2) + Math.random().toString(16).slice(2)
  );
}
