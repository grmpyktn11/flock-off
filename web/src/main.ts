import type { FeatureCollection } from "geojson";

import "@fontsource-variable/space-grotesk";
import "maplibre-gl/dist/maplibre-gl.css";
import "./style.css";

import { mountHeroMap } from "./heroMap";
import { mountTrips, type Demo } from "./tripMap";

const BASE = import.meta.env.BASE_URL;

async function boot(): Promise<void> {
  const [cameras, routes] = await Promise.all([
    fetch(`${BASE}data/cameras.geojson`).then(
      (r) => r.json() as Promise<FeatureCollection>,
    ),
    fetch(`${BASE}data/routes.json`).then(
      (r) => r.json() as Promise<{ demos: Demo[] }>,
    ),
  ]);

  const points = cameras.features.filter(
    (f) => f.properties?.kind === "camera",
  );
  const alpr = points.filter((f) => f.properties?.type === "alpr").length;
  setCount("count-alpr", alpr);
  setCount("count-speed", points.length - alpr);

  mountHeroMap(document.getElementById("hero-map")!, cameras);
  mountTrips(routes.demos);
}

function setCount(id: string, value: number): void {
  const el = document.getElementById(id);
  if (el) el.textContent = value.toLocaleString("en-US");
}

boot();
