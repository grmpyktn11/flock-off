/**
 * A stored trip outlives the code that wrote it.
 *
 * It survives app restarts and app updates, so a field added today is
 * missing from a trip saved yesterday. That already crashed the location
 * task once: lastPosition arrived after a trip was on disk, came back
 * undefined rather than null, and slid past a `=== null` check into the
 * distance maths.
 */
jest.mock("@react-native-async-storage/async-storage", () => {
  let value: string | null = null;
  return {
    __esModule: true,
    default: {
      getItem: jest.fn(async () => value),
      setItem: jest.fn(async (_k: string, v: string) => {
        value = v;
      }),
      removeItem: jest.fn(async () => {
        value = null;
      }),
      __set: (v: string | null) => {
        value = v;
      },
    },
  };
});

import AsyncStorage from "@react-native-async-storage/async-storage";

import { loadTrip } from "../tripStore";

const store = AsyncStorage as unknown as { __set: (v: string | null) => void };

const DESTINATION = { placeId: "p", name: "GMU", address: "", lat: 38.83, lng: -77.31 };
const ROUTE = [{ lat: 38.9, lng: -77.4 }, { lat: 38.85, lng: -77.35 }];

it("fills in fields a previous version never wrote", async () => {
  // Exactly the shape that crashed: no lastPosition, no lastMovedAtMs.
  store.__set(JSON.stringify({ destination: DESTINATION, route: ROUTE }));

  const trip = await loadTrip();
  expect(trip).not.toBeNull();
  expect(trip!.lastPosition).toBeNull();
  expect(typeof trip!.lastMovedAtMs).toBe("number");
  expect(trip!.unavoidable).toEqual([]);
  expect(trip!.announcedCameraIds).toEqual([]);
  expect(trip!.drift.consecutiveOffRoute).toBe(0);
});

it("treats a trip with no destination as no trip", async () => {
  store.__set(JSON.stringify({ route: ROUTE }));
  expect(await loadTrip()).toBeNull();
});

it("treats a trip with no route as no trip", async () => {
  store.__set(JSON.stringify({ destination: DESTINATION }));
  expect(await loadTrip()).toBeNull();
});

it("treats unreadable storage as no trip rather than throwing", async () => {
  store.__set("{not json");
  expect(await loadTrip()).toBeNull();
});

it("returns null when there is nothing stored", async () => {
  store.__set(null);
  expect(await loadTrip()).toBeNull();
});
