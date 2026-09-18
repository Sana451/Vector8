/**
 * RouteLayer component
 *
 * Manages route display on TomTom map.
 * Handles creating/updating GeoJSON source and line layer.
 */

import type { Map as MapLibreMap } from "maplibre-gl"
import { useEffect } from "react"
import type { Coordinate } from "@/lib/routing"

interface RouteLayerProps {
  mapInstance: MapLibreMap | null
  coordinates: Coordinate[] | null
}

const ROUTE_SOURCE_ID = "route"
const ROUTE_LAYER_ID = "route-layer"

/**
 * RouteLayer component
 *
 * Receives map instance and route coordinates.
 * Creates or updates GeoJSON source with LineString feature.
 * Handles cleanup on unmount.
 *
 * @param mapInstance - MapLibre Map instance from TomTom SDK
 * @param coordinates - Array of [longitude, latitude] coordinate pairs
 */
export function RouteLayer({ mapInstance, coordinates }: RouteLayerProps) {
  useEffect(() => {
    if (!mapInstance || !coordinates || coordinates.length < 2) {
      // Remove route if no coordinates
      try {
        if (mapInstance?.getLayer(ROUTE_LAYER_ID)) {
          mapInstance.removeLayer(ROUTE_LAYER_ID)
        }
        if (mapInstance?.getSource(ROUTE_SOURCE_ID)) {
          mapInstance.removeSource(ROUTE_SOURCE_ID)
        }
      } catch (error) {
        console.error("Error removing route layer", error)
      }
      return
    }

    try {
      // Create GeoJSON feature
      const geoJsonFeature = {
        type: "Feature" as const,
        properties: {},
        geometry: {
          type: "LineString" as const,
          coordinates,
        },
      }

      const existingSource = mapInstance.getSource(ROUTE_SOURCE_ID)

      if (existingSource) {
        // Update existing source
        if ("setData" in existingSource) {
          ;(existingSource as { setData: (data: unknown) => void }).setData(
            geoJsonFeature,
          )
        }
      } else {
        // Create new source
        mapInstance.addSource(ROUTE_SOURCE_ID, {
          type: "geojson",
          data: geoJsonFeature,
        })

        // Create layer only if it doesn't exist
        if (!mapInstance.getLayer(ROUTE_LAYER_ID)) {
          mapInstance.addLayer({
            id: ROUTE_LAYER_ID,
            type: "line",
            source: ROUTE_SOURCE_ID,
            layout: {
              "line-cap": "round",
              "line-join": "round",
            },
            paint: {
              "line-color": "#0066cc",
              "line-width": 4,
            },
          })
        }
      }
    } catch (error) {
      console.error("Error updating route layer", error)
    }
  }, [mapInstance, coordinates])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      try {
        if (mapInstance?.getLayer(ROUTE_LAYER_ID)) {
          mapInstance.removeLayer(ROUTE_LAYER_ID)
        }
        if (mapInstance?.getSource(ROUTE_SOURCE_ID)) {
          mapInstance.removeSource(ROUTE_SOURCE_ID)
        }
      } catch (error) {
        console.error("Error cleaning up route layer", error)
      }
    }
  }, [mapInstance])

  return null
}
