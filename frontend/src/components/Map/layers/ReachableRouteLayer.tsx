/**
 * ReachableRouteLayer component
 *
 * Highlights the part of the route the truck can cover on its current fuel
 * from the active walkthrough step (start or refuel/checkpoint station).
 */

import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useMemo } from "react"
import {
  getReachableRouteSegmentMeters,
  type OptimizationStep,
  sliceRouteByDistance,
} from "@/lib/fuelOptimizationWalkthrough"
import { buildRouteFeature } from "@/lib/mapLayers"
import type { Coordinate } from "@/lib/routing"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "reachable-route"
const LAYER_ID = "reachable-route-layer"

interface ReachableRouteLayerProps {
  mapInstance: MapLibreMap | null
  coordinates: Coordinate[] | null
  activeStep: OptimizationStep | null
  consumptionMpg: number
  routeTotalDistanceMeters: number
}

export function ReachableRouteLayer({
  mapInstance,
  coordinates,
  activeStep,
  consumptionMpg,
  routeTotalDistanceMeters,
}: ReachableRouteLayerProps) {
  const data = useMemo(() => {
    if (!coordinates || !activeStep) return null
    const span = getReachableRouteSegmentMeters(
      activeStep,
      consumptionMpg,
      routeTotalDistanceMeters,
    )
    if (!span) return null
    const slice = sliceRouteByDistance(
      coordinates,
      span.startMeters,
      span.endMeters,
    )
    return buildRouteFeature(slice)
  }, [coordinates, activeStep, consumptionMpg, routeTotalDistanceMeters])

  const buildLayers = useCallback(
    (sourceId: string): LayerWithVisibility[] =>
      [
        {
          id: LAYER_ID,
          type: "line",
          source: sourceId,
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": "#16a34a",
            "line-width": 4,
            "line-opacity": 0.85,
          },
        },
      ] as LayerWithVisibility[],
    [],
  )

  useGeoJsonLayer({ mapInstance, sourceId: SOURCE_ID, buildLayers, data })

  return null
}
