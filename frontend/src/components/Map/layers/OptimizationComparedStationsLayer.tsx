/**
 * OptimizationComparedStationsLayer component
 *
 * Highlights on the map the stations that the optimizer weighed against the
 * chosen one (the "Compared with" list in the walkthrough). Rendered only
 * while that list is expanded, so the user does not have to hunt for them.
 */

import type { Feature, FeatureCollection } from "geojson"
import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useMemo } from "react"
import type { FuelOptimizationAlternativePublic } from "@/client"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "optimization-compared-stations"
const HALO_LAYER_ID = "optimization-compared-stations-halo"
const RING_LAYER_ID = "optimization-compared-stations-ring"

const OUTCOME_COLORS: Record<string, string> = {
  not_reachable: "#6b7280",
  overhead_exceeds_savings: "#f59e0b",
  higher_effective_price: "#ef4444",
  tie_broken_by_distance: "#3b82f6",
  no_fuel_to_buy: "#9ca3af",
}
const DEFAULT_COLOR = "#ef4444"

interface OptimizationComparedStationsLayerProps {
  mapInstance: MapLibreMap | null
  alternatives: Array<FuelOptimizationAlternativePublic>
}

function buildFeatures(
  alternatives: Array<FuelOptimizationAlternativePublic>,
): FeatureCollection | null {
  const features: Feature[] = alternatives.map((alternative) => ({
    type: "Feature",
    id: alternative.station_id,
    properties: {
      stationId: alternative.station_id,
      outcome: alternative.outcome,
      cheaper: alternative.cheaper_by_sticker,
    },
    geometry: {
      type: "Point",
      coordinates: [
        Number(alternative.longitude),
        Number(alternative.latitude),
      ],
    },
  }))

  return features.length > 0 ? { type: "FeatureCollection", features } : null
}

export function OptimizationComparedStationsLayer({
  mapInstance,
  alternatives,
}: OptimizationComparedStationsLayerProps) {
  const data = useMemo(() => buildFeatures(alternatives), [alternatives])

  const buildLayers = useCallback((sourceId: string): LayerWithVisibility[] => {
    const color = [
      "match",
      ["get", "outcome"],
      ...Object.entries(OUTCOME_COLORS).flat(),
      DEFAULT_COLOR,
    ]
    return [
      {
        id: HALO_LAYER_ID,
        type: "circle",
        source: sourceId,
        paint: {
          "circle-color": color,
          "circle-radius": 18,
          "circle-opacity": 0.2,
        },
      },
      {
        id: RING_LAYER_ID,
        type: "circle",
        source: sourceId,
        paint: {
          "circle-color": "rgba(255,255,255,0)",
          "circle-radius": 11,
          "circle-stroke-color": color,
          "circle-stroke-width": 3,
          "circle-stroke-opacity": 0.95,
        },
      },
    ] as unknown as LayerWithVisibility[]
  }, [])

  useGeoJsonLayer({ mapInstance, sourceId: SOURCE_ID, buildLayers, data })

  return null
}
