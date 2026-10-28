/**
 * RefinedRouteLayer component
 *
 * Renders the refined route of a trip plan: the route the provider returned
 * after being told to drive into every selected fuel stop. It is drawn on top
 * of the base route with a dashed line so both can be compared visually.
 */

import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useMemo } from "react"
import { buildRouteFeature } from "@/lib/mapLayers"
import type { Coordinate } from "@/lib/routing"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "refined-route"
const CASING_LAYER_ID = "refined-route-casing-layer"
const LAYER_ID = "refined-route-layer"

interface RefinedRouteLayerProps {
  mapInstance: MapLibreMap | null
  coordinates: Coordinate[] | null
}

/**
 * Refined route layer.
 *
 * @param mapInstance - MapLibre Map instance from the TomTom SDK
 * @param coordinates - Array of [longitude, latitude] pairs
 */
export function RefinedRouteLayer({
  mapInstance,
  coordinates,
}: RefinedRouteLayerProps) {
  const data = useMemo(() => buildRouteFeature(coordinates), [coordinates])

  const buildLayers = useCallback(
    (sourceId: string): LayerWithVisibility[] =>
      [
        {
          id: CASING_LAYER_ID,
          type: "line",
          source: sourceId,
          layout: { "line-cap": "butt", "line-join": "round" },
          paint: {
            "line-color": "#ffffff",
            "line-width": 8,
            "line-opacity": 0.6,
          },
        },
        {
          id: LAYER_ID,
          type: "line",
          source: sourceId,
          layout: { "line-cap": "butt", "line-join": "round" },
          paint: {
            "line-color": "#7c3aed",
            "line-width": 4,
            "line-dasharray": [2, 1.5],
          },
        },
      ] as LayerWithVisibility[],
    [],
  )

  useGeoJsonLayer({ mapInstance, sourceId: SOURCE_ID, buildLayers, data })

  return null
}
