/**
 * VehiclePositionsLayer component
 *
 * Renders the last known position of every truck. Color shows the source:
 * GPS sensor, last completed trip, or manual entry.
 */

import type { Feature, FeatureCollection, Point } from "geojson"
import type { Map as MapLibreMap } from "maplibre-gl"
import { useMemo } from "react"

import type { VehiclePositionPublic, VehiclePublic } from "@/client"
import { useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "vehicle-positions-source"
const CIRCLE_LAYER_ID = "vehicle-positions-circle"
const LABEL_LAYER_ID = "vehicle-positions-label"

const SOURCE_COLORS: Record<string, string> = {
  sensor: "#16a34a",
  trip: "#2563eb",
  manual: "#9333ea",
}
const FALLBACK_COLOR = "#64748b"

interface VehiclePositionsLayerProps {
  mapInstance: MapLibreMap | null
  positions: VehiclePositionPublic[]
  vehicles: VehiclePublic[]
}

export function VehiclePositionsLayer({
  mapInstance,
  positions,
  vehicles,
}: VehiclePositionsLayerProps) {
  const data = useMemo<FeatureCollection<Point> | null>(() => {
    if (positions.length === 0) {
      return null
    }
    const vehiclesById = new Map(vehicles.map((v) => [v.id, v]))
    const features: Feature<Point>[] = positions.map((position) => {
      const vehicle = vehiclesById.get(position.vehicle_id)
      const name = vehicle?.unit_number
        ? `${vehicle.name} (${vehicle.unit_number})`
        : (vehicle?.name ?? "Truck")
      return {
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [position.longitude, position.latitude],
        },
        properties: {
          label: name,
          source: position.source,
          color: SOURCE_COLORS[position.source] ?? FALLBACK_COLOR,
          recordedAt: position.recorded_at,
        },
      }
    })
    return { type: "FeatureCollection", features }
  }, [positions, vehicles])

  useGeoJsonLayer({
    mapInstance,
    sourceId: SOURCE_ID,
    data,
    buildLayers: (sourceId) => [
      {
        id: CIRCLE_LAYER_ID,
        type: "circle",
        source: sourceId,
        paint: {
          "circle-color": ["get", "color"],
          "circle-radius": 8,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
        },
      },
      {
        id: LABEL_LAYER_ID,
        type: "symbol",
        source: sourceId,
        layout: {
          "text-field": ["get", "label"],
          "text-size": 11,
          "text-offset": [0, 1.4],
          "text-anchor": "top",
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": "#1e293b",
          "text-halo-color": "#ffffff",
          "text-halo-width": 2,
        },
      },
    ],
  })

  return null
}
