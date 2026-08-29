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
  map.addControl(
    new maplibregl.GeolocateControl({
      positionOptions: { enableHighAccuracy: true },
      trackUserLocation: false,
      showAccuracyCircle: true,
      fitBoundsOptions: { maxZoom: 14 },
    }),
  );

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

function popupHtml(c: CameraProps): string {
  const where = cameraWhere(c);
  const factors = factorLines(c);
  return [
    `<p class="popup-label">${escapeHtml(cameraLabel(c))}</p>`,
    where ? `<p class="popup-where">${escapeHtml(where)}</p>` : "",
    c.usefulness_score !== undefined
      ? `<p class="popup-score"><span>${c.usefulness_score}</span>` +
        `<span class="popup-score-of">/100 ${escapeHtml(c.score_desc ?? "")}</span></p>`
      : "",
    c.explanation
      ? `<p class="popup-why">${escapeHtml(c.explanation)}</p>`
      : "",
    factors.length
      ? `<ul class="popup-factors">${factors
          .map((line) => `<li>${escapeHtml(line)}</li>`)
          .join("")}</ul>`
      : "",
  ].join("");
}
