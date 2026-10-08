/**
 * OptimizationStopsLayer component
 *
 * Renders the fuel optimization walkthrough steps (start, each refuel stop,
 * destination) as numbered markers. The currently active step (driven by
 * the walkthrough Next/Back/jump controls) is highlighted.
 */

import type { Feature, FeatureCollection } from "geojson"
import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useMemo } from "react"
import type { OptimizationStep } from "@/lib/fuelOptimizationWalkthrough"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "optimization-stops"
const CIRCLE_LAYER_ID = "optimization-stops-circle"
const LABEL_LAYER_ID = "optimization-stops-label"

interface OptimizationStopsLayerProps {
  mapInstance: MapLibreMap | null
  steps: OptimizationStep[]
  activeStepIndex: number
}

function stepMarkerLabel(step: OptimizationStep): string {
  if (step.kind === "start") return "S"
  if (step.kind === "destination") return "D"
  return String(step.index)
}

function buildStopsFeatures(
  steps: OptimizationStep[],
  activeStepIndex: number,
): FeatureCollection | null {
  if (steps.length === 0) {
    return null
  }

  const features: Feature[] = steps.map((step) => ({
    type: "Feature",
    id: step.index,
    properties: {
      index: step.index,
      kind: step.kind,
      label: step.label,
      markerLabel: stepMarkerLabel(step),
      isActive: step.index === activeStepIndex,
    },
    geometry: {
      type: "Point",
      coordinates: step.coordinate,
    },
  }))

  return { type: "FeatureCollection", features }
}

/**
 * Numbered markers for the optimization walkthrough steps.
 */
export function OptimizationStopsLayer({
  mapInstance,
  steps,
  activeStepIndex,
}: OptimizationStopsLayerProps) {
  const data = useMemo(
    () => buildStopsFeatures(steps, activeStepIndex),
    [steps, activeStepIndex],
  )

  const buildLayers = useCallback((sourceId: string): LayerWithVisibility[] => {
    return [
      {
        id: CIRCLE_LAYER_ID,
        type: "circle",
        source: sourceId,
        paint: {
          "circle-color": [
            "match",
            ["get", "kind"],
            "start",
            "#2563eb",
            "destination",
            "#7c3aed",
            "#f97316",
          ],
          "circle-radius": ["case", ["get", "isActive"], 14, 10],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": ["case", ["get", "isActive"], 3, 2],
          "circle-opacity": 0.95,
        },
      },
      {
        id: LABEL_LAYER_ID,
        type: "symbol",
        source: sourceId,
        layout: {
          "text-field": ["get", "markerLabel"],
          "text-size": 12,
          "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
        },
        paint: {
          "text-color": "#ffffff",
        },
      },
    ] as unknown as LayerWithVisibility[]
  }, [])

  useGeoJsonLayer({
    mapInstance,
    sourceId: SOURCE_ID,
    buildLayers,
    data,
  })

  return null
}
