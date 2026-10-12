import { length } from "@turf/length"
import type { Feature, FeatureCollection } from "geojson"
import type { Coordinate } from "@/lib/routing"

const KM_PER_MILE = 1.609344

export function measureLengthKm(points: Coordinate[]): number {
  if (points.length < 2) {
    return 0
  }
  return length(
    {
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates: points },
    },
    { units: "kilometers" },
  )
}

export function formatDistance(km: number): string {
  return `${km.toFixed(2)} km (${(km / KM_PER_MILE).toFixed(2)} mi)`
}

/** Line plus a point per vertex (vertices are tagged so they can be styled). */
export function buildMeasureFeatures(
  points: Coordinate[],
  showVertices = true,
): FeatureCollection | null {
  if (points.length === 0) {
    return null
  }
  const features: Feature[] = []
  if (points.length >= 2) {
    features.push({
      type: "Feature",
      properties: { kind: "line" },
      geometry: { type: "LineString", coordinates: points },
    })
  }
  if (showVertices) {
    for (const coordinates of points) {
      features.push({
        type: "Feature",
        properties: { kind: "vertex" },
        geometry: { type: "Point", coordinates },
      })
    }
  }
  return { type: "FeatureCollection", features }
}

/** Skip freehand samples closer than `minMeters` to the previous one. */
export function shouldAddFreehandPoint(
  last: Coordinate | undefined,
  next: Coordinate,
  minMeters = 20,
): boolean {
  if (!last) {
    return true
  }
  return measureLengthKm([last, next]) * 1000 >= minMeters
}
