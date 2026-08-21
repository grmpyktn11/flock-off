import { Camera, Place, Plan } from "./types";

// Stand-in for GET /search and POST /plan. Everything here is fake data for
// the Fairfax / Herndon test region so the app can be built and demoed
// without the backend running.

const PLACES: Place[] = [
  {
    placeId: "mock-reston-town-center",
    description: "Reston Town Center, Reston, VA",
    lat: 38.9586,
    lng: -77.3571,
  },
  {
    placeId: "mock-herndon-metro",
    description: "Herndon Metro Station, Herndon, VA",
    lat: 38.9476,
    lng: -77.3399,
  },
  {
    placeId: "mock-fairfax-corner",
    description: "Fairfax Corner, Fairfax, VA",
    lat: 38.8637,
    lng: -77.3616,
  },
  {
    placeId: "mock-dulles-airport",
    description: "Washington Dulles International Airport, Dulles, VA",
    lat: 38.9531,
    lng: -77.4565,
  },
  {
    placeId: "mock-vienna-metro",
    description: "Vienna Metro Station, Vienna, VA",
    lat: 38.8776,
    lng: -77.2719,
  },
  {
    placeId: "mock-tysons-corner",
    description: "Tysons Corner Center, Tysons, VA",
    lat: 38.9179,
    lng: -77.2214,
  },
];

const CAMERAS: Camera[] = [
  { id: "cam-1", type: "alpr", lat: 38.9503, lng: -77.3488, avoided: true },
  { id: "cam-2", type: "alpr", lat: 38.9412, lng: -77.3302, avoided: true },
  { id: "cam-3", type: "speed_camera", lat: 38.9218, lng: -77.3105, avoided: true },
  { id: "cam-4", type: "alpr", lat: 38.8991, lng: -77.2884, avoided: false },
];

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function searchPlaces(query: string): Promise<Place[]> {
  await delay(250);
  const trimmed = query.trim().toLowerCase();
  if (trimmed.length === 0) {
    return [];
  }
  return PLACES.filter((place) =>
    place.description.toLowerCase().includes(trimmed)
  );
}

export async function planRoute(
  origin: Place,
  destination: Place
): Promise<Plan> {
  await delay(900);

  const avoided = CAMERAS.filter((camera) => camera.avoided);
  const unavoidable = CAMERAS.filter((camera) => !camera.avoided);
  const baselineEtaMinutes = 24;
  const avoidanceEtaMinutes = 31;

  return {
    deepLinkUrl: buildDeepLinkUrl(origin, destination, MOCK_WAYPOINTS),
    origin,
    destination,
    cameras: CAMERAS,
    avoidedCount: avoided.length,
    unavoidableCount: unavoidable.length,
    baselineEtaMinutes,
    avoidanceEtaMinutes,
    etaDeltaMinutes: avoidanceEtaMinutes - baselineEtaMinutes,
    routePolyline: "mock_polyline",
  };
}

const MOCK_WAYPOINTS = [
  { lat: 38.9445, lng: -77.3521 },
  { lat: 38.9127, lng: -77.3184 },
];

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
