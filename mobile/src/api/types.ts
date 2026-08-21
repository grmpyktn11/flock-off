// Shapes mirror the backend contract in final-spec.md. The app is built
// against mocks until the real FastAPI service exists.

export type Place = {
  placeId: string;
  description: string;
  lat: number;
  lng: number;
};

export type CameraType = "alpr" | "speed_camera";

export type Camera = {
  id: string;
  type: CameraType;
  lat: number;
  lng: number;
  // False means the route still passes this camera and the driver gets an
  // audio alert while driving.
  avoided: boolean;
};

// Response body of POST /plan.
export type Plan = {
  deepLinkUrl: string;
  origin: Place;
  destination: Place;
  cameras: Camera[];
  avoidedCount: number;
  unavoidableCount: number;
  baselineEtaMinutes: number;
  avoidanceEtaMinutes: number;
  etaDeltaMinutes: number;
  routePolyline: string;
};
