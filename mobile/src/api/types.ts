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
  // Context from OSM, when a mapper recorded it: who operates the camera,
  // whose product it is, and the road it watches. The point of the app is
  // as much awareness as avoidance, and "a Flock Safety reader run by the
  // county police on Lee Highway" carries that; a pin on a map does not.
  operator: string | null;
  brand: string | null;
  roadName: string | null;
  roadRef: string | null;
  // Public-records factors and the computed usefulness score, null where
  // the jurisdiction publishes nothing. The desc strings name the source
  // and scope, e.g. "reported incidents within half a mile ... (DC MPD)".
  crimeCount: number | null;
  crimeDesc: string | null;
  arrestCount: number | null;
  arrestDesc: string | null;
  tractIncome: number | null;
  countyIncome: number | null;
  usefulnessScore: number | null;
  scoreDesc: string | null;
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
