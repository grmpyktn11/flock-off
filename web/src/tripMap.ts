import type { Feature } from "geojson";
import maplibregl from "maplibre-gl";

import {
  cameraLabel,
  cameraWhere,
  escapeHtml,
  minutes,
  type CameraProps,
} from "./copy";
import { decodePolyline } from "./polyline";
import { isDark, mapStyle, onThemeChange } from "./theme";

const RASPBERRY = "#cc3a63";

export interface DemoCamera extends CameraProps {
  id: number;
  lat: number;
  lng: number;
  avoided: boolean;
  // On the route Google would have driven. An in-view camera without this
  // flag is one the detour itself picked up, and the copy says so rather
  // than pretending it was always going to be there.
  on_baseline: boolean;
}

export interface Demo {
  origin: { name: string; lat: number; lng: number };
  destination: { name: string; lat: number; lng: number };
  baseline_polyline: string;
  route_polyline: string;
  cameras: DemoCamera[];
  avoided_count: number;
  unavoidable_count: number;
  baseline_eta_seconds: number;
  route_eta_seconds: number;
  eta_delta_seconds: number;
}

export function mountTrips(demos: Demo[]): void {
  const tabs = document.querySelector(".trip-tabs") as HTMLElement;
  const verdict = document.getElementById("trip-verdict") as HTMLElement;
  const list = document.getElementById("trip-cameras") as HTMLElement;

  const map = new maplibregl.Map({
    container: "trip-map",
    style: mapStyle(),
    center: [-77.25, 38.87],
    zoom: 10,
    cooperativeGestures: true,
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }));

  let ready = false;
  let selected = 0;

  // Sources and layers are wiped by a style swap, so they are (re)built
  // on every style.load: startup and each theme toggle.
  map.on("style.load", () => {
    const olive = isDark() ? "#a2ab73" : "#6f7847";
    const baseline = isDark() ? "#8c8574" : "#a49c8c";
    const ground = isDark() ? "#1c1a14" : "#fff7eb";

    map.addSource("baseline", { type: "geojson", data: emptyLine() });
    map.addSource("detour", { type: "geojson", data: emptyLine() });
    map.addSource("trip-cameras", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });

    map.addLayer({
      id: "baseline-line",
      type: "line",
      source: "baseline",
      paint: {
        "line-color": baseline,
        "line-width": 3.5,
        "line-dasharray": [2, 1.6],
      },
    });
    map.addLayer({
      id: "detour-line",
      type: "line",
      source: "detour",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": olive, "line-width": 4.5 },
    });
    map.addLayer({
      id: "trip-camera-dots",
      type: "circle",
      source: "trip-cameras",
      paint: {
        "circle-color": ["case", ["get", "avoided"], "#a2ab73", RASPBERRY],
        "circle-radius": 7,
        "circle-stroke-color": ground,
        "circle-stroke-width": 2,
      },
    });

    ready = true;
    show(selected);
  });

  onThemeChange(() => map.setStyle(mapStyle()));

  map.on("click", "trip-camera-dots", (e) => {
    const feature = e.features?.[0];
    if (!feature) return;
    const c = feature.properties as DemoCamera;
    new maplibregl.Popup({ closeButton: false })
      .setLngLat(e.lngLat)
      .setHTML(`<p class="popup-label">${escapeHtml(cameraLabel(c))}</p>`)
      .addTo(map);
  });

  demos.forEach((demo, i) => {
    const tab = document.createElement("button");
    tab.className = "trip-tab";
    tab.setAttribute("role", "tab");
    tab.textContent = `${demo.origin.name} to ${demo.destination.name}`;
    tab.addEventListener("click", () => {
      selected = i;
      tabs
        .querySelectorAll(".trip-tab")
        .forEach((t, j) => t.setAttribute("aria-selected", String(j === i)));
      if (ready) show(i);
    });
    tab.setAttribute("aria-selected", String(i === 0));
    tabs.appendChild(tab);
  });

  function show(i: number): void {
    const demo = demos[i];
    const baseline = decodePolyline(demo.baseline_polyline);
    const detour = decodePolyline(demo.route_polyline);

    (map.getSource("baseline") as maplibregl.GeoJSONSource).setData(
      lineFeature(baseline),
    );
    (map.getSource("detour") as maplibregl.GeoJSONSource).setData(
      lineFeature(detour),
    );
    (map.getSource("trip-cameras") as maplibregl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features: demo.cameras.map((c) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [c.lng, c.lat] },
        properties: { ...c },
      })),
    });

    const bounds = new maplibregl.LngLatBounds();
    for (const point of [...baseline, ...detour]) bounds.extend(point);
    map.fitBounds(bounds, { padding: 48, duration: 600 });

    verdict.innerHTML = verdictHtml(demo);
    list.innerHTML = "";
    for (const c of [...demo.cameras].sort(
      (a, b) => Number(b.avoided) - Number(a.avoided),
    )) {
      const item = document.createElement("li");
      if (c.avoided) item.classList.add("avoided");
      const where = cameraWhere(c);
      item.innerHTML =
        `<span class="status">${statusLabel(c)}</span><br>` +
        `${escapeHtml(cameraLabel(c))}` +
        (where ? `<br><span class="where">${escapeHtml(where)}</span>` : "");
      list.appendChild(item);
    }
  }
}

function statusLabel(c: DemoCamera): string {
  if (c.avoided) return "Dodged";
  return c.on_baseline ? "Sees you either way" : "New on the detour";
}

function verdictHtml(demo: Demo): string {
  const base = Math.round(demo.baseline_eta_seconds / 60);
  const onBaseline = demo.cameras.filter((c) => c.on_baseline).length;
  const inView = demo.cameras.filter((c) => !c.avoided);
  const pickedUp = inView.filter((c) => !c.on_baseline).length;

  if (demo.avoided_count === 0) {
    return (
      `None of the ${plural(onBaseline, "camera")} on this ` +
      `${base}-minute trip can be routed around, and the plan says so.`
    );
  }

  const drives =
    `Google drives this ${base}-minute trip past ` +
    `${plural(onBaseline, "camera")}.`;
  const cost =
    demo.eta_delta_seconds <= 0
      ? "and is no slower"
      : `<span class="delta">for ${minutes(demo.eta_delta_seconds)} more</span>`;
  const dodges = ` The detour dodges ${
    demo.avoided_count === onBaseline ? "all of them" : demo.avoided_count
  } ${cost}.`;
  let sees = "";
  if (inView.length > 0) {
    sees = ` ${plural(inView.length, "camera")} still ${
      inView.length === 1 ? "sees" : "see"
    } it.`;
    if (pickedUp > 0) {
      const which =
        pickedUp === inView.length
          ? pickedUp === 1
            ? "That one is a reader"
            : "All of those are readers"
          : pickedUp === 1
            ? "One of those is a reader"
            : `${pickedUp} of those are readers`;
      sees += ` ${which} the detour itself drives past.`;
    }
  }
  return drives + dodges + sees;
}

function plural(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

function emptyLine(): Feature {
  return lineFeature([]);
}

function lineFeature(coordinates: [number, number][]): Feature {
  return {
    type: "Feature",
    geometry: { type: "LineString", coordinates },
    properties: {},
  };
}
