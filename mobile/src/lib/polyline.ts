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
