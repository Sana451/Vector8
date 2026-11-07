/**
 * ShipmentPickupLayer component
 *
 * Renders the selected shipment's pickup point as an intermediate optimizer
 * waypoint. The start comes from the vehicle and the finish from the dropoff,
 * so this point is the only one shown as a separate marker.
 */

import type { Feature, Point } from "geojson"
import type { Map as MapLibreMap } from "maplibre-gl"
import { useMemo } from "react"

import type { AddressSelection } from "@/lib/mapRequest"
import { useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "shipment-pickup-source"
const CIRCLE_LAYER_ID = "shipment-pickup-circle"
const LABEL_LAYER_ID = "shipment-pickup-label"
const PICKUP_COLOR = "#f59e0b"

interface ShipmentPickupLayerProps {
  mapInstance: MapLibreMap | null
  pickup: AddressSelection | null
}

export function ShipmentPickupLayer({
  mapInstance,
  pickup,
}: ShipmentPickupLayerProps) {
  const data = useMemo<Feature<Point> | null>(() => {
    const coordinates = pickup?.location?.coordinates
    if (!pickup || !coordinates) {
      return null
    }
    return {
      type: "Feature",
      geometry: { type: "Point", coordinates: [...coordinates] },
      properties: {
        label: "Погрузка",
        address: pickup.formatted_address,
      },
    }
  }, [pickup])

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
          "circle-color": PICKUP_COLOR,
          "circle-radius": 11,
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
          "text-size": 12,
          "text-offset": [0, 1.6],
          "text-anchor": "top",
          "text-allow-overlap": true,
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
