// The backend contract. These mirror app/schemas.py on the FastAPI side,
// converted from snake_case to camelCase and nothing else.
//
// ETAs stay in seconds, the unit the backend sends. Rounding to whole
// minutes here would throw away precision in the one number the user is
// being asked to accept, so the screens round only at the point of display.

// An autocomplete suggestion. No coordinates: resolving one costs Google
// a Place Details call, so only the suggestion the driver picks gets
// resolved, through placeDetails().
export type PlaceSuggestion = {
  placeId: string;
  name: string;
  address: string;
};

export type Place = PlaceSuggestion & {
  lat: number;
  lng: number;
};

export type CameraType = "alpr" | "speed_camera";

export type Camera = {
  id: number;
  type: CameraType;
  lat: number;
  lng: number;
  facingDeg: number | null;
  // False means the route still passes this camera and the driver gets an
  // audio alert while driving.
  avoided: boolean;
};

export type Waypoint = {
  lat: number;
  lng: number;
  nearestCameraM: number;
};

// Response body of POST /plan. Origin and destination are not echoed back;
// the caller already has them.
export type Plan = {
  deepLinkUrl: string;
  routePolyline: string;
  waypoints: Waypoint[];
  // Only cameras one of the two routes actually drove into. Cameras merely
  // near the trip are left out, so avoidedCount means work done rather than
  // how big the search box was.
  cameras: Camera[];
  avoidedCount: number;
  unavoidableCount: number;
  baselineEtaSeconds: number;
  routeEtaSeconds: number;
  etaDeltaSeconds: number;
};
