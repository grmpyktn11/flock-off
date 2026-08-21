// Deciding when the driver has left the planned route, and when that is
// worth interrupting them over.
//
// Two separate questions, deliberately kept apart:
//
//   1. Are we off route? Pure geometry, answered here every GPS tick.
//   2. Is a re-plan worth offering? Answered by the backend, because only
//      it knows whether a route from here would dodge any cameras.
//
// The second question is the important one. Google reroutes for traffic
// all the time, and most of those reroutes are harmless. Prompting on
// every drift would train the driver to dismiss the prompt.

import { distanceToRouteMeters } from "./geo";
import { LatLng } from "./polyline";

// From the spec: 100m off the route for three consecutive ticks.
export const OFF_ROUTE_METERS = 100;
export const CONSECUTIVE_TICKS = 3;

// Re-planning costs a network round trip and, if accepted, throws the
// driver out of navigation and back in. Both are worth rationing.
export const CHECK_COOLDOWN_MS = 2 * 60 * 1000;
export const MAX_PROMPTS_PER_TRIP = 3;

export type DriftState = {
  consecutiveOffRoute: number;
  promptsShown: number;
  lastCheckAtMs: number | null;
};

export const initialDriftState: DriftState = {
  consecutiveOffRoute: 0,
  promptsShown: 0,
  lastCheckAtMs: null,
};

export type DriftTick = {
  state: DriftState;
  // True means ask the backend whether a re-plan from here is worth it.
  // It does not mean prompt the driver; that needs the answer first.
  shouldCheck: boolean;
  distanceMeters: number;
};

export function onLocation(
  state: DriftState,
  position: LatLng,
  route: LatLng[],
  nowMs: number
): DriftTick {
  const distanceMeters = distanceToRouteMeters(position, route);

  if (distanceMeters <= OFF_ROUTE_METERS) {
    // Back on the route. Reset, so a later excursion has to earn its own
    // three ticks rather than inheriting credit from this one.
    return {
      state: { ...state, consecutiveOffRoute: 0 },
      shouldCheck: false,
      distanceMeters,
    };
  }

  const consecutiveOffRoute = state.consecutiveOffRoute + 1;
  const next = { ...state, consecutiveOffRoute };

  const settled = consecutiveOffRoute >= CONSECUTIVE_TICKS;
  const underCap = state.promptsShown < MAX_PROMPTS_PER_TRIP;
  const cooledDown =
    state.lastCheckAtMs === null || nowMs - state.lastCheckAtMs >= CHECK_COOLDOWN_MS;

  if (!settled || !underCap || !cooledDown) {
    return { state: next, shouldCheck: false, distanceMeters };
  }

  return {
    state: { ...next, lastCheckAtMs: nowMs },
    shouldCheck: true,
    distanceMeters,
  };
}

/**
 * Whether the re-plan the backend just returned is worth showing.
 *
 * A re-plan that avoids nothing means Google's current path is already as
 * good as anything we would propose, so the driver hears nothing.
 */
export function isWorthPrompting(avoidedCount: number): boolean {
  return avoidedCount > 0;
}

export function recordPromptShown(state: DriftState): DriftState {
  return { ...state, promptsShown: state.promptsShown + 1 };
}

/** After the driver accepts, the new route replaces the old one. */
export function onReplanAccepted(state: DriftState): DriftState {
  return { ...state, consecutiveOffRoute: 0 };
}
