// Stand-in for GET /search and POST /plan, used when EXPO_PUBLIC_API_URL is
// unset. Fake data for the Fairfax / Herndon test region so the app can be
// built and demoed without the backend running.

import { Camera, Place, Plan } from "./types";

const PLACES: Place[] = [
  {
    placeId: "mock-reston-town-center",
    name: "Reston Town Center",
    address: "11900 Market St, Reston, VA",
    lat: 38.9586,
    lng: -77.3571,
  },
  {
    placeId: "mock-herndon-metro",
    name: "Herndon Metro Station",
    address: "585 Herndon Pkwy, Herndon, VA",
    lat: 38.9476,
    lng: -77.3399,
  },
  {
    placeId: "mock-fairfax-corner",
    name: "Fairfax Corner",
    address: "11900 Palace Way, Fairfax, VA",
    lat: 38.8637,
    lng: -77.3616,
  },
  {
    placeId: "mock-dulles-airport",
    name: "Washington Dulles International Airport",
    address: "1 Saarinen Cir, Dulles, VA",
    lat: 38.9531,
    lng: -77.4565,
  },
  {
    placeId: "mock-vienna-metro",
    name: "Vienna Metro Station",
    address: "9550 Saintsbury Dr, Fairfax, VA",
    lat: 38.8776,
    lng: -77.2719,
  },
  {
    placeId: "mock-tysons-corner",
    name: "Tysons Corner Center",
    address: "1961 Chain Bridge Rd, Tysons, VA",
    lat: 38.9179,
    lng: -77.2214,
  },
];

const CAMERAS: Camera[] = [
  { id: 1, type: "alpr", lat: 38.9503, lng: -77.3488, facingDeg: 90, avoided: true },
  { id: 2, type: "alpr", lat: 38.9412, lng: -77.3302, facingDeg: null, avoided: true },
  { id: 3, type: "speed_camera", lat: 38.9218, lng: -77.3105, facingDeg: 270, avoided: true },
  { id: 4, type: "alpr", lat: 38.8991, lng: -77.2884, facingDeg: 180, avoided: false },
];

const MOCK_WAYPOINTS = [
  { lat: 38.9445, lng: -77.3521, nearestCameraM: 180.4 },
  { lat: 38.9127, lng: -77.3184, nearestCameraM: 220.9 },
];

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function searchPlaces(
  query: string,
  near?: { lat: number; lng: number }
): Promise<Place[]> {
  await delay(250);
  const trimmed = query.trim().toLowerCase();
  if (trimmed.length === 0) {
    return [];
  }
  const matches = PLACES.filter(
    (place) =>
      place.name.toLowerCase().includes(trimmed) ||
      place.address.toLowerCase().includes(trimmed)
  );
  if (near) {
    matches.sort(
      (a, b) =>
        Math.hypot(a.lat - near.lat, a.lng - near.lng) -
        Math.hypot(b.lat - near.lat, b.lng - near.lng)
    );
  }
  return matches;
}

export async function planRoute(
  origin: Place,
  destination: Place
): Promise<Plan> {
  await delay(900);

  const avoided = CAMERAS.filter((camera) => camera.avoided);
  const unavoidable = CAMERAS.filter((camera) => !camera.avoided);
  const baselineEtaSeconds = 1440;
  const routeEtaSeconds = 1860;

  return {
    deepLinkUrl: buildDeepLinkUrl(origin, destination, MOCK_WAYPOINTS),
    routePolyline: "mock_polyline",
    waypoints: MOCK_WAYPOINTS,
    cameras: CAMERAS,
    avoidedCount: avoided.length,
    unavoidableCount: unavoidable.length,
    baselineEtaSeconds,
    routeEtaSeconds,
    etaDeltaSeconds: routeEtaSeconds - baselineEtaSeconds,
  };
}

export async function replanRoute(
  current: { lat: number; lng: number },
  destination: Place
): Promise<Plan> {
  const from: Place = {
    placeId: "mock-current-position",
    name: "Current position",
    address: "",
    ...current,
  };
  return planRoute(from, destination);
}

// The real deep link is built by the backend after it picks waypoints. It is
// rebuilt here so the mock returns a link that actually opens Google Maps.
function buildDeepLinkUrl(
  origin: Place,
  destination: Place,
  waypoints: { lat: number; lng: number }[]
): string {
  const params = new URLSearchParams({
    api: "1",
    origin: `${origin.lat},${origin.lng}`,
    destination: `${destination.lat},${destination.lng}`,
    travelmode: "driving",
  });
  if (waypoints.length > 0) {
    params.set(
      "waypoints",
      waypoints.map((point) => `${point.lat},${point.lng}`).join("|")
    );
  }
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}
