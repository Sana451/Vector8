/**
 * DetourLayer component
 *
 * Renders the detour zone (buffer) around the route as a semi-transparent polygon.
 * Updates in real-time as the detour distance slider changes.
 */

import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useMemo } from "react"
import { buildDetourFeature } from "@/lib/mapLayers"
import type { Coordinate } from "@/lib/routing"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "detour"
const LAYER_ID = "detour-layer"

interface DetourLayerProps {
  mapInstance: MapLibreMap | null
  coordinates: Coordinate[] | null
  detourMeters: number
}

/**
 * Detour layer - shows the zone around the route where detours are allowed.
 *
 * @param mapInstance - MapLibre Map instance from the TomTom SDK
 * @param coordinates - Array of [longitude, latitude] pairs
 * @param detourMeters - Detour distance in meters
 */
export function DetourLayer({
  mapInstance,
  coordinates,
  detourMeters,
}: DetourLayerProps) {
  // Convert meters to kilometers for the buffer function
  const detourKm = detourMeters / 1000

  // Build detour feature - updates whenever coordinates or detour distance changes
  const data = useMemo(
    () => buildDetourFeature(coordinates, detourKm),
    [coordinates, detourKm],
  )

  const buildLayers = useCallback(
    (sourceId: string): LayerWithVisibility[] =>
      [
        {
          id: LAYER_ID,
          type: "fill",
          source: sourceId,
          layout: {},
          paint: {
            "fill-color": "#3b82f6",
            "fill-opacity": 0.1,
          },
        },
        {
          id: `${LAYER_ID}-stroke`,
          type: "line",
          source: sourceId,
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#3b82f6",
            "line-width": 1,
            "line-opacity": 0.4,
            "line-dasharray": [4, 4],
          },
        },
      ] as LayerWithVisibility[],
    [],
  )

  useGeoJsonLayer({ mapInstance, sourceId: SOURCE_ID, buildLayers, data })

  return null
}
