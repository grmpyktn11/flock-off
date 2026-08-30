// What a camera is and where it is, in words. Mirrors the app's
// cameraCopy.ts: "Flock Safety on Lee Highway, run by the county police"
// is the version worth knowing, not a coordinate pair.

export interface CameraProps {
  type: string;
  brand?: string;
  operator?: string;
  road_name?: string;
  road_ref?: string;
  crime_count?: number;
  crime_desc?: string;
  arrest_count?: number;
  arrest_desc?: string;
  tract_income?: number;
  county_income?: number;
  usefulness_score?: number;
  score_desc?: string;
}

// One line per factor the public record actually holds. The desc strings
// already carry their own source and scope, so nothing is invented on the
// way out. Mirrors factorLines() in the app.
export function factorLines(c: CameraProps): string[] {
  const lines: string[] = [];
  if (c.crime_count !== undefined && c.crime_desc) {
    lines.push(`Crime: ${c.crime_count} ${c.crime_desc}`);
  }
  if (c.arrest_count !== undefined && c.arrest_desc) {
    lines.push(`Arrests: ${c.arrest_count} ${c.arrest_desc}`);
  }
  if (c.tract_income !== undefined) {
    const county =
      c.county_income !== undefined
        ? ` vs ${dollars(c.county_income)} county median`
        : "";
    lines.push(`Income: ${dollars(c.tract_income)} here${county} (US Census ACS)`);
  }
  return lines;
}

// The Census top-codes wealthy tracts as 250001, meaning "$250,000+".
function dollars(income: number): string {
  return income >= 250001 ? "$250,000+" : `$${income.toLocaleString("en-US")}`;
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
  // Past an hour and a half, minutes stop meaning anything to a reader.
  if (seconds >= 5400) return `${(seconds / 3600).toFixed(1)} hours`;
  const m = seconds / 60;
  return `${m < 10 ? m.toFixed(1) : Math.round(m)} minutes`;
}
