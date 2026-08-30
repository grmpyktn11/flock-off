import type { FeatureCollection } from "geojson";
import maplibregl from "maplibre-gl";

import {
  cameraLabel,
  cameraWhere,
  escapeHtml,
  factorLines,
  type CameraProps,
} from "./copy";
import { isDark, mapStyle, onThemeChange } from "./theme";

// Northern Virginia and DC, where the density is. The full DMV bbox is
// two states wide; the first frame should show cameras, not geography.
const START_BOUNDS: [[number, number], [number, number]] = [
  [-77.65, 38.72],
  [-76.85, 39.12],
];

const RASPBERRY = "#cc3a63";

export function mountHeroMap(
  container: HTMLElement,
  cameras: FeatureCollection,
): void {
  // On a phone the sheet covers the bottom of the map, so the cameras
  // are fitted into the strip that stays visible rather than the whole
  // canvas. The map itself stays full-bleed behind the sheet.
  const phone = window.matchMedia("(max-width: 640px)").matches;
  const padding = phone
    ? { top: 88, bottom: Math.round(window.innerHeight * 0.45), left: 24, right: 24 }
    : 40;

  const map = new maplibregl.Map({
    container,
    style: mapStyle(),
    bounds: START_BOUNDS,
    fitBoundsOptions: { padding },
    cooperativeGestures: true,
    attributionControl: { compact: true },
  });
  if (!phone) {
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }));
  }

  // "What is near me?" is the first question this map invites, and the
  // answer is the whole point of it. Denial is not an error worth
  // reporting: the map stays where it is and the DMV is still visible.
  //
  // The control's own zoom lands on the user's street, which on a quiet
  // block answers the question with an empty map. So after it locates,
  // the view is refit to hold the user and their nearest cameras
  // together - the neighborhood's coverage, not the doorstep.
  const geolocate = new maplibregl.GeolocateControl({
    positionOptions: { enableHighAccuracy: true },
    trackUserLocation: false,
    showAccuracyCircle: true,
    fitBoundsOptions: { maxZoom: 14 },
  });
  map.addControl(geolocate);
  geolocate.on("geolocate", (position) => {
    const here: [number, number] = [
      position.coords.longitude,
      position.coords.latitude,
    ];
    const bounds = nearbyCameraBounds(cameras, here);
    if (bounds) {
      map.fitBounds(bounds, { padding, maxZoom: 13, duration: 1200 });
    }
  });

  // A style swap wipes sources and layers, so everything is added on
  // style.load: once at startup, and again on every theme toggle.
  map.on("style.load", () => {
    const ground = isDark() ? "#1c1a14" : "#fff7eb";
    map.addSource("cameras", { type: "geojson", data: cameras });

    // The dead zones are ~23m road slices, invisible until street level.
    map.addLayer({
      id: "dead-zones",
      type: "fill",
      source: "cameras",
      filter: ["==", ["get", "kind"], "dead_zone"],
      minzoom: 12,
      paint: {
        "fill-color": RASPBERRY,
        "fill-opacity": 0.22,
        "fill-outline-color": RASPBERRY,
      },
    });

    map.addLayer({
      id: "cameras-speed",
      type: "circle",
      source: "cameras",
      filter: [
        "all",
        ["==", ["get", "kind"], "camera"],
        ["!=", ["get", "type"], "alpr"],
      ],
      paint: {
        "circle-color": ground,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 2, 12, 5],
        "circle-stroke-color": RASPBERRY,
        "circle-stroke-width": 1.5,
      },
    });

    map.addLayer({
      id: "cameras-alpr",
      type: "circle",
      source: "cameras",
      filter: [
        "all",
        ["==", ["get", "kind"], "camera"],
        ["==", ["get", "type"], "alpr"],
      ],
      paint: {
        "circle-color": RASPBERRY,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 2.5, 12, 6],
        "circle-opacity": 0.85,
      },
    });
  });

  onThemeChange(() => map.setStyle(mapStyle()));

  for (const layer of ["cameras-alpr", "cameras-speed"]) {
    map.on("click", layer, (e) => {
      const feature = e.features?.[0];
      if (!feature) return;
      const props = feature.properties as CameraProps;
      new maplibregl.Popup({ closeButton: false })
        .setLngLat(e.lngLat)
        .setHTML(popupHtml(props))
        .addTo(map);
    });
    map.on("mouseenter", layer, () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", layer, () => {
      map.getCanvas().style.cursor = "";
    });
  }
}

// Enough dots to read as "my area is covered" without hunting for them.
const NEARBY_CAMERAS = 12;
// Past this a camera is not "near" in any sense a resident would accept,
// and fitting to it would zoom out to geography instead of neighborhood.
// It also keeps a visitor from far outside the DMV from being flown to a
// county-spanning frame: with no cameras in range the control's own
// street-level zoom stands.
const NEARBY_MAX_KM = 30;

function nearbyCameraBounds(
  cameras: FeatureCollection,
  here: [number, number],
): maplibregl.LngLatBounds | null {
  const kmPerLng = 111.32 * Math.cos((here[1] * Math.PI) / 180);
  const nearest = cameras.features
    .filter(
      (f) => f.properties?.kind === "camera" && f.geometry.type === "Point",
    )
    .map((f) => {
      const [lng, lat] = (f.geometry as GeoJSON.Point).coordinates;
      const km = Math.hypot((lng - here[0]) * kmPerLng, (lat - here[1]) * 111.32);
      return { lng, lat, km };
    })
    .filter((c) => c.km <= NEARBY_MAX_KM)
    .sort((a, b) => a.km - b.km)
    .slice(0, NEARBY_CAMERAS);
  if (nearest.length === 0) return null;

  const bounds = new maplibregl.LngLatBounds(here, here);
  for (const c of nearest) bounds.extend([c.lng, c.lat]);
  return bounds;
}

// The app's camera card, minus its AI explanation: the deterministic
// score out of 100 (accented when low, like the app), how many factors
// carried it, and one line per factor the public record holds. A camera
// without a score says so instead of showing nothing - thin public data
// is itself the finding.
function popupHtml(c: CameraProps): string {
  const where = cameraWhere(c);
  const factors = factorLines(c);
  const score =
    c.usefulness_score !== undefined
      ? `<p class="popup-score${c.usefulness_score < 30 ? " low" : ""}">` +
        `<span>${c.usefulness_score}</span>` +
        `<span class="popup-score-of">/100 useful score</span></p>`
      : `<p class="popup-score-none">Useful score: not enough public data</p>`;
  return [
    `<p class="popup-label">${escapeHtml(cameraLabel(c))}</p>`,
    where ? `<p class="popup-where">${escapeHtml(where)}</p>` : "",
    score,
    c.score_desc
      ? `<p class="popup-score-desc">${escapeHtml(c.score_desc)}</p>`
      : "",
    factors.length
      ? `<ul class="popup-factors">${factors
          .map((line) => `<li>${escapeHtml(line)}</li>`)
          .join("")}</ul>`
      : "",
  ].join("");
}
