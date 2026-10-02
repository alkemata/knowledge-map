import type { LatLngExpression, LatLngTuple } from "leaflet";

export type WorldPoint = { x: number; y: number };

export function worldToLeaflet(point: WorldPoint): LatLngTuple {
  return [point.y, point.x];
}

export function leafletToWorld(point: { lat: number; lng: number }): WorldPoint {
  return { x: point.lng, y: point.lat };
}

export function pointsToLeaflet(points: [number, number][]): LatLngExpression[] {
  return points.map(([x, y]) => [y, x] as LatLngTuple);
}

export function svgY(y: number, regionMaxY: number): number {
  return regionMaxY - y;
}
