/**
 * RoutePointsLayer component
 *
 * Always shows the start (pickup) and finish (delivery) points currently
 * entered in the route form, so the map reflects the form values.
 */

import type { Feature, FeatureCollection, Point } from "geojson"
import type { Map as MapLibreMap } from "maplibre-gl"
import { useMemo } from "react"

import type { GeoJSONPoint } from "@/client"
import { useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "route-points-source"
const CIRCLE_LAYER_ID = "route-points-circle"
const LABEL_LAYER_ID = "route-points-label"

interface RoutePointsLayerProps {
  mapInstance: MapLibreMap | null
  pickup: GeoJSONPoint | null
  delivery: GeoJSONPoint | null
}

function toFeature(
  point: GeoJSONPoint,
  kind: "start" | "finish",
): Feature<Point> {
  return {
    type: "Feature",
    geometry: { type: "Point", coordinates: [...point.coordinates] },
    properties: {
      kind,
      label: kind === "start" ? "Старт" : "Финиш",
      color: kind === "start" ? "#22c55e" : "#ef4444",
    },
  }
}

export function RoutePointsLayer({
  mapInstance,
  pickup,
  delivery,
}: RoutePointsLayerProps) {
  const data = useMemo<FeatureCollection<Point> | null>(() => {
    const features: Array<Feature<Point>> = []
    if (pickup?.coordinates) {
      features.push(toFeature(pickup, "start"))
    }
    if (delivery?.coordinates) {
      features.push(toFeature(delivery, "finish"))
    }
    if (features.length === 0) {
      return null
    }
    return { type: "FeatureCollection", features }
  }, [pickup, delivery])

  useGeoJsonLayer({
    mapInstance,
    sourceId: SOURCE_ID,
    data,
    buildLayers: (sourceId) => [
      {
        id: CIRCLE_LAYER_ID,
        type: "circle",
        source: sourceId,
        paint: {
          "circle-color": ["get", "color"],
          "circle-radius": 9,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
        },
      },
      {
        id: LABEL_LAYER_ID,
        type: "symbol",
        source: sourceId,
        layout: {
          "text-field": ["get", "label"],
          "text-size": 12,
          "text-offset": [0, 1.6],
          "text-anchor": "top",
          "text-allow-overlap": true,
        },
        paint: {
          "text-color": "#1e293b",
          "text-halo-color": "#ffffff",
          "text-halo-width": 2,
        },
      },
    ],
  })

  return null
}
