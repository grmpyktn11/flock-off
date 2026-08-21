// The real backend. Implements the same two functions as mockBackend.ts,
// so swapping between them is a config change and the screens never know
// which one they are talking to.

import { API_BASE_URL, REQUEST_TIMEOUT_MS } from "./config";
import { Camera, CameraType, Place, Plan, Waypoint } from "./types";

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
  near?: { lat: number; lng: number }
): Promise<Place[]> {
  const trimmed = query.trim();
  if (trimmed.length === 0) {
    return [];
  }

  const params = new URLSearchParams({ q: trimmed });
  if (near) {
    params.set("lat", String(near.lat));
    params.set("lng", String(near.lng));
  }

  const body = await request(`/search?${params.toString()}`);
  return (body.results as unknown[]).map(toPlace);
}

export async function planRoute(
  origin: Place,
  destination: Place
): Promise<Plan> {
  const body = await request("/plan", {
    origin: { lat: origin.lat, lng: origin.lng },
    destination: { lat: destination.lat, lng: destination.lng },
  });
  return toPlan(body);
}

async function request(path: string, json?: unknown): Promise<any> {
  // React Native has no default request timeout, so a server that accepts
  // the connection and then stalls would hang the screen forever.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: json === undefined ? "GET" : "POST",
      headers: json === undefined ? undefined : { "Content-Type": "application/json" },
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
    throw new ApiError(
      `The server answered ${response.status}.`,
      response.status >= 500
    );
  }

  try {
    return await response.json();
  } catch {
    throw new ApiError("The server sent a response we could not read.", false);
  }
}

function toPlace(raw: any): Place {
  return {
    placeId: raw.place_id,
    name: raw.name,
    address: raw.address,
    lat: raw.lat,
    lng: raw.lng,
  };
}

function toCamera(raw: any): Camera {
  return {
    id: raw.id,
    type: raw.type as CameraType,
    lat: raw.lat,
    lng: raw.lng,
    facingDeg: raw.facing_deg ?? null,
    avoided: raw.avoided,
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
