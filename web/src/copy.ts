// What a camera is and where it is, in words. Mirrors the app's
// cameraCopy.ts: "Flock Safety on Lee Highway, run by the county police"
// is the version worth knowing, not a coordinate pair.

export interface CameraProps {
  type: string;
  brand?: string;
  operator?: string;
  road_name?: string;
  road_ref?: string;
  explanation?: string;
}

export function cameraLabel(c: CameraProps): string {
  const kind = c.type === "alpr" ? "License plate reader" : "Speed camera";
  return c.brand ? `${kind} · ${c.brand}` : kind;
}

export function cameraWhere(c: CameraProps): string {
  const parts: string[] = [];
  if (c.road_name || c.road_ref) {
    const road = c.road_name ?? c.road_ref;
    const ref = c.road_name && c.road_ref ? ` (${c.road_ref})` : "";
    parts.push(`On ${road}${ref}`);
  }
  if (c.operator) {
    parts.push(`operated by ${c.operator}`);
  }
  const text = parts.join(", ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Road names, operators and brands come from OSM; never trust them as HTML.
export function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

export function minutes(seconds: number): string {
  if (seconds < 60) return `${seconds} seconds`;
  const m = seconds / 60;
  return `${m < 10 ? m.toFixed(1) : Math.round(m)} minutes`;
}
