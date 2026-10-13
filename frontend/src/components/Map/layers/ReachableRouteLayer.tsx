/**
 * ReachableRouteLayer component
 *
 * Highlights the part of the route the truck can cover on its current fuel
 * from the active walkthrough step (start or refuel/checkpoint station).
 */

import type { Feature, FeatureCollection, LineString } from "geojson"
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
const RESERVE_BASE_LAYER_ID = "reachable-route-reserve-base-layer"
const RESERVE_STRIPE_LAYER_ID = "reachable-route-reserve-stripe-layer"

const SEGMENT_KIND = {
  usable: "usable",
  reserve: "reserve",
} as const

interface ReachableRouteLayerProps {
  mapInstance: MapLibreMap | null
  coordinates: Coordinate[] | null
  activeStep: OptimizationStep | null
  consumptionMpg: number
  routeTotalDistanceMeters: number
  reserveGallons: number
}

function buildSegmentFeature(
  coordinates: Coordinate[],
  kind: (typeof SEGMENT_KIND)[keyof typeof SEGMENT_KIND],
): Feature<LineString> | null {
  const feature = buildRouteFeature(coordinates)
  if (!feature) return null
  return { ...feature, properties: { kind } } as Feature<LineString>
}

export function ReachableRouteLayer({
  mapInstance,
  coordinates,
  activeStep,
  consumptionMpg,
  routeTotalDistanceMeters,
  reserveGallons,
}: ReachableRouteLayerProps) {
  const data = useMemo<FeatureCollection<LineString> | null>(() => {
    if (!coordinates || !activeStep) return null
    const span = getReachableRouteSegmentMeters(
      activeStep,
      consumptionMpg,
      routeTotalDistanceMeters,
      reserveGallons,
    )
    if (!span) return null

    const features = [
      buildSegmentFeature(
        sliceRouteByDistance(
          coordinates,
          span.startMeters,
          span.reserveStartMeters,
        ),
        SEGMENT_KIND.usable,
      ),
      buildSegmentFeature(
        sliceRouteByDistance(
          coordinates,
          span.reserveStartMeters,
          span.endMeters,
        ),
        SEGMENT_KIND.reserve,
      ),
    ].filter((feature): feature is Feature<LineString> => feature !== null)

    if (features.length === 0) return null
    return { type: "FeatureCollection", features }
  }, [
    coordinates,
    activeStep,
    consumptionMpg,
    routeTotalDistanceMeters,
    reserveGallons,
  ])

  const buildLayers = useCallback(
    (sourceId: string): LayerWithVisibility[] =>
      [
        {
          id: LAYER_ID,
          type: "line",
          source: sourceId,
          filter: ["==", ["get", "kind"], SEGMENT_KIND.usable],
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": "#16a34a",
            "line-width": 4,
            "line-opacity": 0.85,
          },
        },
        {
          id: RESERVE_BASE_LAYER_ID,
          type: "line",
          source: sourceId,
          filter: ["==", ["get", "kind"], SEGMENT_KIND.reserve],
          layout: { "line-cap": "butt", "line-join": "round" },
          paint: {
            "line-color": "#dc2626",
            "line-width": 4,
            "line-opacity": 0.85,
          },
        },
        {
          id: RESERVE_STRIPE_LAYER_ID,
          type: "line",
          source: sourceId,
          filter: ["==", ["get", "kind"], SEGMENT_KIND.reserve],
          layout: { "line-cap": "butt", "line-join": "round" },
          paint: {
            "line-color": "#16a34a",
            "line-width": 4,
            "line-opacity": 0.85,
            "line-dasharray": [2, 2],
          },
        },
      ] as LayerWithVisibility[],
    [],
  )

  useGeoJsonLayer({ mapInstance, sourceId: SOURCE_ID, buildLayers, data })

  return null
}
