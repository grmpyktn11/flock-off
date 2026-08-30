// The real backend. Implements the same two functions as mockBackend.ts,
// so swapping between them is a config change and the screens never know
// which one they are talking to.

import {
  API_BASE_URL,
  APP_KEY,
  REQUEST_TIMEOUT_MS,
  SLOW_REQUEST_TIMEOUT_MS,
} from "./config";
import { Camera, CameraType, Place, PlaceSuggestion, Plan, Waypoint } from "./types";

export class ApiError extends Error {
  // True when retrying might work: a timeout, a dropped connection, or a
  // 5xx. False for a request the server rejected outright.
  readonly retryable: boolean;

  constructor(message: string, retryable: boolean) {
    super(message);
    this.name = "ApiError";
    this.retryable = retryable;
  }
}

export async function searchPlaces(
  query: string,
  near?: { lat: number; lng: number },
  sessionToken?: string
): Promise<PlaceSuggestion[]> {
  const trimmed = query.trim();
  if (trimmed.length === 0) {
    return [];
  }

  const params = new URLSearchParams({ q: trimmed });
  if (near) {
    params.set("lat", String(near.lat));
    params.set("lng", String(near.lng));
  }
  if (sessionToken) {
    params.set("session_token", sessionToken);
  }

  const body = await request(`/search?${params.toString()}`);
  return (body.results as unknown[]).map(toSuggestion);
}

/**
 * Resolve a chosen suggestion to coordinates.
 *
 * Passing the same token the search used closes Google's session, so the
 * whole keystroke burst plus this call bills as one instead of per
 * request. Call it once, when the driver picks a place.
 */
export async function placeDetails(
  placeId: string,
  sessionToken?: string
): Promise<Place> {
  const params = new URLSearchParams({ place_id: placeId });
  if (sessionToken) {
    params.set("session_token", sessionToken);
  }
  return toPlace(await request(`/place?${params.toString()}`));
}

export async function planRoute(
  origin: Place,
  destination: Place
): Promise<Plan> {
  const body = await request(
    "/plan",
    {
      origin: { lat: origin.lat, lng: origin.lng },
      destination: { lat: destination.lat, lng: destination.lng },
      // Only used to label the deep link. Without them Google names the
      // endpoints after whatever it finds nearest the coordinate.
      origin_place_id: origin.placeId,
      destination_place_id: destination.placeId,
    },
    SLOW_REQUEST_TIMEOUT_MS
  );
  return toPlan(body);
}

// Same pipeline as planRoute, started from wherever the driver is now.
// Used when drift detection sees us leave the planned route.
export async function replanRoute(
  current: { lat: number; lng: number },
  destination: Place
): Promise<Plan> {
  const body = await request(
    "/replan",
    {
      current,
      destination: { lat: destination.lat, lng: destination.lng },
      destination_place_id: destination.placeId,
    },
    SLOW_REQUEST_TIMEOUT_MS
  );
  return toPlan(body);
}

/**
 * Why each of these cameras is plausibly where it is, keyed by camera id.
 *
 * One batch per plan. Ids the backend could not explain are simply absent
 * from the result, so callers show what they got.
 */
export async function cameraExplanations(
  cameraIds: number[]
): Promise<Record<number, string>> {
  if (cameraIds.length === 0) {
    return {};
  }
  const body = await request(
    "/explanations",
    { camera_ids: cameraIds },
    SLOW_REQUEST_TIMEOUT_MS
  );
  return body.explanations as Record<number, string>;
}

async function request(
  path: string,
  json?: unknown,
  timeoutMs: number = REQUEST_TIMEOUT_MS
): Promise<any> {
  // React Native has no default request timeout, so a server that accepts
  // the connection and then stalls would hang the screen forever.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const headers: Record<string, string> = {};
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (APP_KEY) {
    headers["X-App-Key"] = APP_KEY;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: json === undefined ? "GET" : "POST",
      headers,
      body: json === undefined ? undefined : JSON.stringify(json),
      signal: controller.signal,
    });
  } catch (cause) {
    const timedOut = controller.signal.aborted;
    throw new ApiError(
      timedOut ? "The server took too long to answer." : "Could not reach the server.",
      true
    );
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    // 429 is the one 4xx worth retrying: it means "later", not "no". The
    // backend sends Retry-After with it, and a driver who waits a moment
    // and taps again is doing exactly the right thing.
    const retryable = response.status >= 500 || response.status === 429;
    throw new ApiError(await failureMessage(response), retryable);
  }

  try {
    return await response.json();
  } catch {
    throw new ApiError("The server sent a response we could not read.", false);
  }
}

/**
 * The backend's own words where it has any.
 *
 * It answers 503 with a detail explaining that routing is down, which is
 * more use to the driver than a status code.
 */
async function failureMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string" && body.detail.length > 0) {
      return body.detail;
    }
  } catch {
    // No JSON body, or not the shape we expected. Fall through.
  }
  return `The server answered ${response.status}.`;
}

function toSuggestion(raw: any): PlaceSuggestion {
  return { placeId: raw.place_id, name: raw.name, address: raw.address };
}

function toPlace(raw: any): Place {
  return { ...toSuggestion(raw), lat: raw.lat, lng: raw.lng };
}

function toCamera(raw: any): Camera {
  return {
    id: raw.id,
    type: raw.type as CameraType,
    lat: raw.lat,
    lng: raw.lng,
    facingDeg: raw.facing_deg ?? null,
    avoided: raw.avoided,
    operator: raw.operator ?? null,
    brand: raw.brand ?? null,
    roadName: raw.road_name ?? null,
    roadRef: raw.road_ref ?? null,
    crimeCount: raw.crime_count ?? null,
    crimeDesc: raw.crime_desc ?? null,
    arrestCount: raw.arrest_count ?? null,
    arrestDesc: raw.arrest_desc ?? null,
    tractIncome: raw.tract_income ?? null,
    countyIncome: raw.county_income ?? null,
    usefulnessScore: raw.usefulness_score ?? null,
    scoreDesc: raw.score_desc ?? null,
  };
}

function toWaypoint(raw: any): Waypoint {
  return { lat: raw.lat, lng: raw.lng, nearestCameraM: raw.nearest_camera_m };
}

function toPlan(raw: any): Plan {
  return {
    deepLinkUrl: raw.deep_link,
    routePolyline: raw.route_polyline,
    waypoints: (raw.waypoints as unknown[]).map(toWaypoint),
    cameras: (raw.cameras as unknown[]).map(toCamera),
    avoidedCount: raw.avoided_count,
    unavoidableCount: raw.unavoidable_count,
    baselineEtaSeconds: raw.baseline_eta_seconds,
    routeEtaSeconds: raw.route_eta_seconds,
    etaDeltaSeconds: raw.eta_delta_seconds,
  };
}
