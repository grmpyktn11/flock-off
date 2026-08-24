// Stand-in for GET /search and POST /plan, used when EXPO_PUBLIC_API_URL is
// unset. Fake data for the Fairfax / Herndon test region so the app can be
// built and demoed without the backend running.

import { Camera, Place, PlaceSuggestion, Plan } from "./types";
import { haversineMeters } from "../lib/geo";
import { LatLng, encodePolyline } from "../lib/polyline";
import { offsetPerpendicular, positionAt, routeLengthMeters } from "../lib/simulate";

const PLACES: Place[] = [
  {
    placeId: "mock-gmu",
    name: "George Mason University",
    address: "4400 University Dr, Fairfax, VA",
    lat: 38.8304,
    lng: -77.3078,
  },
  {
    placeId: "mock-lincoln-memorial",
    name: "Lincoln Memorial",
    address: "2 Lincoln Memorial Cir NW, Washington, DC",
    lat: 38.8893,
    lng: -77.0502,
  },
  {
    placeId: "mock-union-station",
    name: "Union Station",
    address: "50 Massachusetts Ave NE, Washington, DC",
    lat: 38.8977,
    lng: -77.0063,
  },
  {
    placeId: "mock-georgetown",
    name: "Georgetown Waterfront",
    address: "3303 Water St NW, Washington, DC",
    lat: 38.9033,
    lng: -77.0657,
  },
  {
    placeId: "mock-nats-park",
    name: "Nationals Park",
    address: "1500 S Capitol St SE, Washington, DC",
    lat: 38.8730,
    lng: -77.0074,
  },
  {
    placeId: "mock-reston-town-center",
    name: "Reston Town Center",
    address: "11900 Market St, Reston, VA",
    lat: 38.9586,
    lng: -77.3571,
  },
  {
    placeId: "mock-vienna-metro",
    name: "Vienna Metro Station",
    address: "9550 Saintsbury Dr, Fairfax, VA",
    lat: 38.8776,
    lng: -77.2719,
  },
];

// Cameras are described by where they sit on the route rather than by
// fixed coordinates, because the route is now generated from whichever
// pair of places was picked. An offset of zero puts the camera on the
// line, which is what makes it unavoidable; anything else puts it far
// enough to the side that the detour genuinely misses it.
const CAMERA_PLACEMENTS = [
  { id: 1, type: "alpr", atFraction: 0.18, offsetMeters: 240, facingDeg: 90,
    operator: "Fairfax County Police Department", brand: "Flock Safety",
    roadName: "Lee Highway", roadRef: "US 29" },
  { id: 2, type: "alpr", atFraction: 0.37, offsetMeters: 300, facingDeg: null,
    operator: "Fairfax County Police Department", brand: "Flock Safety",
    roadName: "Chain Bridge Road", roadRef: "VA 123" },
  { id: 3, type: "speed_camera", atFraction: 0.55, offsetMeters: 260, facingDeg: 270,
    operator: "City of Falls Church", brand: null,
    roadName: "Arlington Boulevard", roadRef: "US 50" },
  { id: 4, type: "alpr", atFraction: 0.72, offsetMeters: 0, facingDeg: 180,
    operator: "Metropolitan Police Department", brand: "Flock Safety",
    roadName: "Constitution Avenue NW", roadRef: null },
] as const;

// Where the detour hangs, between the cameras it is dodging.
const WAYPOINT_FRACTIONS = [0.27, 0.46];

// A straight line between two places is not a route, and the drift and
// alert thresholds were tuned against something that bends. This bows the
// line sideways - zero at both ends, widest in the middle - and samples it
// often enough that a simulated drive has somewhere to be on every tick.
const BOW_FRACTION = 0.08;
const POINT_SPACING_M = 100;

// About 30 mph, the same figure the drive simulator defaults to.
const AVERAGE_SPEED_MPS = 13.4;

function mockRoute(origin: LatLng, destination: LatLng): LatLng[] {
  const straight = haversineMeters(origin, destination);
  const steps = Math.max(2, Math.round(straight / POINT_SPACING_M));

  const dLat = destination.lat - origin.lat;
  const dLng = destination.lng - origin.lng;
  const length = Math.hypot(dLat, dLng);
  const perpLat = length === 0 ? 0 : -dLng / length;
  const perpLng = length === 0 ? 0 : dLat / length;

  const degreesPerMeter = 1 / 111320;
  const cosLat = Math.cos((origin.lat * Math.PI) / 180);
  const bow = straight * BOW_FRACTION;

  const points: LatLng[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const sideways = Math.sin(t * Math.PI) * bow * degreesPerMeter;
    points.push({
      lat: origin.lat + dLat * t + perpLat * sideways,
      lng: origin.lng + dLng * t + (perpLng * sideways) / cosLat,
    });
  }
  return points;
}

function camerasFor(route: LatLng[], totalMeters: number): Camera[] {
  return CAMERA_PLACEMENTS.map((placement) => {
    const along = totalMeters * placement.atFraction;
    const point =
      placement.offsetMeters === 0
        ? positionAt(route, along)
        : offsetPerpendicular(route, along, placement.offsetMeters);
    return {
      id: placement.id,
      type: placement.type,
      lat: point.lat,
      lng: point.lng,
      facingDeg: placement.facingDeg,
      avoided: placement.offsetMeters > 0,
      operator: placement.operator,
      brand: placement.brand,
      roadName: placement.roadName,
      roadRef: placement.roadRef,
    };
  });
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function placeDetails(
  placeId: string,
  _sessionToken?: string
): Promise<Place> {
  await delay(120);
  const place = PLACES.find((p) => p.placeId === placeId);
  if (!place) {
    throw new Error(`unknown place ${placeId}`);
  }
  return place;
}

export async function searchPlaces(
  query: string,
  near?: { lat: number; lng: number },
  _sessionToken?: string
): Promise<PlaceSuggestion[]> {
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
  // The real Autocomplete returns no coordinates, so neither does this.
  return matches.map(({ placeId, name, address }) => ({ placeId, name, address }));
}

export async function planRoute(
  origin: Place,
  destination: Place,
  _strict = false
): Promise<Plan> {
  await delay(900);

  const route = mockRoute(origin, destination);
  const routeMeters = routeLengthMeters(route);
  const cameras = camerasFor(route, routeMeters);

  const waypoints = WAYPOINT_FRACTIONS.map((fraction) => {
    const point = positionAt(route, routeMeters * fraction);
    const nearestCameraM = Math.min(
      ...cameras.map((camera) =>
        haversineMeters(point, { lat: camera.lat, lng: camera.lng })
      )
    );
    return { ...point, nearestCameraM: Math.round(nearestCameraM * 10) / 10 };
  });

  // The detour costs what the extra distance costs, rather than a number
  // picked to look good - the bow in the route is where it comes from.
  const straightMeters = haversineMeters(origin, destination);

  return {
    deepLinkUrl: buildDeepLinkUrl(origin, destination, waypoints),
    routePolyline: encodePolyline(route),
    waypoints,
    cameras,
    avoidedCount: cameras.filter((camera) => camera.avoided).length,
    unavoidableCount: cameras.filter((camera) => !camera.avoided).length,
    baselineEtaSeconds: Math.round(straightMeters / AVERAGE_SPEED_MPS),
    routeEtaSeconds: Math.round(routeMeters / AVERAGE_SPEED_MPS),
    etaDeltaSeconds: Math.round(
      (routeMeters - straightMeters) / AVERAGE_SPEED_MPS
    ),
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
