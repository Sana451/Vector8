/**
 * TruckRestrictionLayer component
 *
 * Renders truck restrictions (bridge clearances, weight limits) as warning
 * markers along the route.
 */

import type { LayerSpecification, Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useMemo } from "react"
import type { TruckRestrictionData } from "@/client"
import { buildTruckRestrictionFeatures } from "@/lib/mapLayers"
import { useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "truck-restrictions"
const CIRCLE_LAYER_ID = "truck-restrictions-layer"
const LABEL_LAYER_ID = "truck-restrictions-label"

interface TruckRestrictionLayerProps {
  mapInstance: MapLibreMap | null
  restrictions: Array<TruckRestrictionData> | undefined
}

/**
 * Truck restriction layer.
 *
 * @param mapInstance - MapLibre Map instance from the TomTom SDK
 * @param restrictions - Truck restrictions from the map overview response
 */
export function TruckRestrictionLayer({
  mapInstance,
  restrictions,
}: TruckRestrictionLayerProps) {
  const data = useMemo(
    () => buildTruckRestrictionFeatures(restrictions),
    [restrictions],
  )

  const buildLayers = useCallback(
    (sourceId: string): LayerSpecification[] => [
      {
        id: CIRCLE_LAYER_ID,
        type: "circle",
        source: sourceId,
        paint: {
          "circle-radius": 7,
          "circle-color": [
            "match",
            ["get", "restrictionType"],
            "bridge_height",
            "#7c3aed",
            "weight_limit",
            "#dc2626",
            "no_trucks",
            "#991b1b",
            "hazmat",
            "#d97706",
            "#475569",
          ],
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
        },
      },
      {
        id: LABEL_LAYER_ID,
        type: "symbol",
        source: sourceId,
        layout: {
          "text-field": ["get", "restrictionType"],
          "text-size": 10,
          "text-offset": [0, 1.4],
          "text-anchor": "top",
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": "#1e293b",
          "text-halo-color": "#ffffff",
          "text-halo-width": 1,
        },
      },
    ],
    [],
  )

  useGeoJsonLayer({ mapInstance, sourceId: SOURCE_ID, buildLayers, data })

  return null
}
