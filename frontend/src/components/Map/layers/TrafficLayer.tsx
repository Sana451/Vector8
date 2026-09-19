/**
 * TrafficLayer component
 *
 * Renders traffic incidents as severity-coloured circles.
 */

import type { LayerSpecification, Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useMemo } from "react"
import type { TrafficLayerData } from "@/client"
import { buildTrafficFeatures } from "@/lib/mapLayers"
import { useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "traffic"
const LAYER_ID = "traffic-layer"

interface TrafficLayerProps {
  mapInstance: MapLibreMap | null
  traffic: TrafficLayerData | null | undefined
}

/**
 * Traffic layer.
 *
 * @param mapInstance - MapLibre Map instance from the TomTom SDK
 * @param traffic - Traffic payload from the map overview response
 */
export function TrafficLayer({ mapInstance, traffic }: TrafficLayerProps) {
  const data = useMemo(() => buildTrafficFeatures(traffic), [traffic])

  const buildLayers = useCallback(
    (sourceId: string): LayerSpecification[] => [
      {
        id: LAYER_ID,
        type: "circle",
        source: sourceId,
        paint: {
          "circle-radius": 6,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
          "circle-color": [
            "match",
            ["get", "severity"],
            "severe",
            "#b91c1c",
            "major",
            "#ea580c",
            "moderate",
            "#f59e0b",
            "minor",
            "#fbbf24",
            "#9ca3af",
          ],
        },
      },
    ],
    [],
  )

  useGeoJsonLayer({ mapInstance, sourceId: SOURCE_ID, buildLayers, data })

  return null
}
