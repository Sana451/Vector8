/**
 * RouteLayer component
 *
 * Renders the calculated route as a line on the map.
 */

import type { LayerSpecification, Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useMemo } from "react"
import { buildRouteFeature } from "@/lib/mapLayers"
import type { Coordinate } from "@/lib/routing"
import { useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "route"
const LAYER_ID = "route-layer"

interface RouteLayerProps {
  mapInstance: MapLibreMap | null
  coordinates: Coordinate[] | null
}

/**
 * Route layer.
 *
 * @param mapInstance - MapLibre Map instance from the TomTom SDK
 * @param coordinates - Array of [longitude, latitude] pairs
 */
export function RouteLayer({ mapInstance, coordinates }: RouteLayerProps) {
  const data = useMemo(() => buildRouteFeature(coordinates), [coordinates])

  const buildLayers = useCallback(
    (sourceId: string): LayerSpecification[] => [
      {
        id: LAYER_ID,
        type: "line",
        source: sourceId,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#0066cc", "line-width": 4 },
      },
    ],
    [],
  )

  useGeoJsonLayer({ mapInstance, sourceId: SOURCE_ID, buildLayers, data })

  return null
}
