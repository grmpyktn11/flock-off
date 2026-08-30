// Where a camera is and what it is, in words. Shared by the plan screen's
// list and the cameras tab, so the two never describe the same camera
// differently.

import { Camera, Plan } from "../api/types";
import { haversineMeters } from "./geo";
import { decodePolyline } from "./polyline";

// Where the camera is in words: the road it watches when OSM names one,
// then how far into the trip the driver meets it, then who operates it.
// A latitude and longitude tells them nothing they can use from behind a
// wheel; "Flock Safety on Lee Highway, run by the county police" is the
// version worth knowing - and worth repeating to a county board meeting.
export function describeCamera(camera: Camera, plan: Plan): string {
  const parts = [];
  if (camera.roadName || camera.roadRef) {
    const road = camera.roadName ?? camera.roadRef;
    const ref =
      camera.roadName && camera.roadRef ? ` (${camera.roadRef})` : "";
    parts.push(`On ${road}${ref}`);
  }
  parts.push(distanceAlong(camera, plan));
  if (camera.operator) {
    parts.push(`Operated by ${camera.operator}`);
  }
  const text = parts.join(" · ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function distanceAlong(camera: Camera, plan: Plan): string {
  const route = decodePolyline(plan.routePolyline);
  let travelled = 0;
  let best = { distance: Infinity, along: 0 };
  for (let i = 0; i < route.length - 1; i++) {
    const step = haversineMeters(route[i], route[i + 1]);
    const distance = haversineMeters(route[i], { lat: camera.lat, lng: camera.lng });
    if (distance < best.distance) best = { distance, along: travelled };
    travelled += step;
  }
  const miles = best.along / 1609.34;
  return miles < 0.6
    ? "near the start of the route"
    : `about ${miles.toFixed(1)} mi in`;
}

// The camera's factor breakdown, one line per factor the public record
// actually holds. The desc strings already carry source and scope, so
// these read "Crime: 189 reported incidents within half a mile ... (DC
// MPD)" with nothing invented on the way.
export function factorLines(camera: Camera): string[] {
  const lines: string[] = [];
  if (camera.crimeCount !== null && camera.crimeDesc) {
    lines.push(`Crime: ${camera.crimeCount} ${camera.crimeDesc}`);
  }
  if (camera.arrestCount !== null && camera.arrestDesc) {
    lines.push(`Arrests: ${camera.arrestCount} ${camera.arrestDesc}`);
  }
  if (camera.tractIncome !== null) {
    const county =
      camera.countyIncome !== null
        ? ` vs ${dollars(camera.countyIncome)} county median`
        : "";
    lines.push(
      `Income: ${dollars(camera.tractIncome)} here${county} (US Census ACS)`
    );
  }
  return lines;
}

// The Census top-codes wealthy tracts as 250001, meaning "$250,000+".
function dollars(income: number): string {
  return income >= 250001 ? "$250,000+" : `$${income.toLocaleString("en-US")}`;
}

export function cameraLabel(camera: Camera): string {
  const kind =
    camera.type === "alpr" ? "License plate reader" : "Speed camera";
  return camera.brand ? `${kind} — ${camera.brand}` : kind;
}
