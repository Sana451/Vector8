/**
 * FuelLayer component
 *
 * Renders fuel stations along the route as circles with price labels.
 */

import type { LayerSpecification, Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useMemo } from "react"
import type { FuelStationData } from "@/client"
import { buildFuelFeatures } from "@/lib/mapLayers"
import { useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "fuel-stations"
const CIRCLE_LAYER_ID = "fuel-stations-layer"
const LABEL_LAYER_ID = "fuel-stations-label"

interface FuelLayerProps {
  mapInstance: MapLibreMap | null
  stations: Array<FuelStationData> | undefined
}

/**
 * Fuel station layer.
 *
 * @param mapInstance - MapLibre Map instance from the TomTom SDK
 * @param stations - Fuel stations from the map overview response
 */
export function FuelLayer({ mapInstance, stations }: FuelLayerProps) {
  const data = useMemo(() => buildFuelFeatures(stations), [stations])

  const buildLayers = useCallback(
    (sourceId: string): LayerSpecification[] => [
      {
        id: CIRCLE_LAYER_ID,
        type: "circle",
        source: sourceId,
        paint: {
          "circle-radius": 7,
          "circle-color": [
            "case",
            ["get", "truckAccessible"],
            "#15803d",
            "#94a3b8",
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
          "text-field": ["coalesce", ["get", "brand"], ["get", "name"]],
          "text-size": 11,
          "text-offset": [0, 1.4],
          "text-anchor": "top",
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": "#14532d",
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
