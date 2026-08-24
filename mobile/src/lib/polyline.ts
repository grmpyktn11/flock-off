// Decoder for the encoded polyline the backend sends as routePolyline.
// The backend encodes at precision 5; Valhalla's native precision 6 never
// reaches the app, because the backend re-encodes before responding.

export type LatLng = { lat: number; lng: number };

export function decodePolyline(encoded: string, precision = 5): LatLng[] {
  const points: LatLng[] = [];
  const scale = Math.pow(10, precision);
  let index = 0;
  let lat = 0;
  let lng = 0;

  while (index < encoded.length) {
    for (const isLat of [true, false]) {
      let result = 0;
      let shift = 0;
      let byte: number;
      do {
        byte = encoded.charCodeAt(index++) - 63;
        result |= (byte & 0x1f) << shift;
        shift += 5;
      } while (byte >= 0x20);
      const delta = result & 1 ? ~(result >> 1) : result >> 1;
      if (isLat) {
        lat += delta;
      } else {
        lng += delta;
      }
    }
    points.push({ lat: lat / scale, lng: lng / scale });
  }
  return points;
}

// The inverse, used only by the mock backend so an offline demo has a
// route with real geometry to drive along. Nothing in the live path
// encodes - the backend does that.
export function encodePolyline(points: LatLng[], precision = 5): string {
  const scale = Math.pow(10, precision);
  let lat = 0;
  let lng = 0;
  let out = "";

  for (const point of points) {
    const nextLat = Math.round(point.lat * scale);
    const nextLng = Math.round(point.lng * scale);
    out += encodeSigned(nextLat - lat) + encodeSigned(nextLng - lng);
    lat = nextLat;
    lng = nextLng;
  }
  return out;
}

function encodeSigned(delta: number): string {
  let value = delta < 0 ? ~(delta << 1) : delta << 1;
  let out = "";
  while (value >= 0x20) {
    out += String.fromCharCode((0x20 | (value & 0x1f)) + 63);
    value >>>= 5;
  }
  return out + String.fromCharCode(value + 63);
}
