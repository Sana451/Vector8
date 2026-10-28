/**
 * TripStopsLayer component
 *
 * Renders the frozen trip stops as numbered markers. Unlike the optimizer's
 * walkthrough layer this one has no notion of an active step: a saved trip is
 * read-only, so every stop is drawn the same way.
 */

import type { Feature, FeatureCollection } from "geojson"
import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useMemo } from "react"

import type { TripPlanStopSnapshot } from "@/client"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "trip-stops"
const CIRCLE_LAYER_ID = "trip-stops-circle"
const LABEL_LAYER_ID = "trip-stops-label"

interface TripStopsLayerProps {
  mapInstance: MapLibreMap | null
  stops: TripPlanStopSnapshot[]
}

function markerLabel(stop: TripPlanStopSnapshot): string {
  if (stop.kind === "start") return "S"
  if (stop.kind === "destination") return "D"
  return String(stop.sequence)
}

function buildFeatures(
  stops: TripPlanStopSnapshot[],
): FeatureCollection | null {
  if (stops.length === 0) {
    return null
  }

  const features: Feature[] = stops.map((stop) => ({
    type: "Feature",
    id: stop.sequence,
    properties: {
      kind: stop.kind,
      label: stop.label,
      markerLabel: markerLabel(stop),
    },
    geometry: { type: "Point", coordinates: stop.coordinate },
  }))

  return { type: "FeatureCollection", features }
}

/**
 * Trip stop markers.
 *
 * @param mapInstance - MapLibre Map instance from the TomTom SDK
 * @param stops - Frozen stop snapshots in travel order
 */
export function TripStopsLayer({ mapInstance, stops }: TripStopsLayerProps) {
  const data = useMemo(() => buildFeatures(stops), [stops])

  const buildLayers = useCallback(
    (sourceId: string): LayerWithVisibility[] => [
      {
        id: CIRCLE_LAYER_ID,
        type: "circle",
        source: sourceId,
        paint: {
          "circle-radius": 11,
          "circle-color": [
            "match",
            ["get", "kind"],
            "start",
            "#16a34a",
            "destination",
            "#dc2626",
            "#7c3aed",
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      },
      {
        id: LABEL_LAYER_ID,
        type: "symbol",
        source: sourceId,
        layout: {
          "text-field": ["get", "markerLabel"],
          "text-size": 12,
          "text-allow-overlap": true,
        },
        paint: { "text-color": "#ffffff" },
      },
    ],
    [],
  )

  useGeoJsonLayer({ mapInstance, sourceId: SOURCE_ID, buildLayers, data })

  return null
}
