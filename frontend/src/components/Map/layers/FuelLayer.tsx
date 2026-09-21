/**
 * FuelLayer component
 *
 * Renders fuel stations as drop-shaped markers.
 * Shape = type (fuel drop), Color = availability
 */

import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useEffect, useMemo } from "react"
import type { FuelStationData } from "@/client"
import {
  mapObjectZoom,
  shouldShowClusters,
  shouldShowMapObjects,
  shouldShowObjectLabels,
} from "@/lib/mapLayerInteraction"
import { buildFuelFeatures } from "@/lib/mapLayers"
import { colorPalette, markerIcons } from "@/lib/mapMarkerIcons"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "fuel-stations"
const DROP_LAYER_ID = "fuel-stations-drops"
const LABEL_LAYER_ID = "fuel-stations-label"
const CLUSTER_CIRCLE_LAYER_ID = "fuel-cluster-circle"
const CLUSTER_TEXT_LAYER_ID = "fuel-cluster-text"

interface FuelLayerProps {
  mapInstance: MapLibreMap | null
  stations: Array<FuelStationData> | undefined
}

/**
 * Fuel station layer with drop markers.
 */
export function FuelLayer({ mapInstance, stations }: FuelLayerProps) {
  const data = useMemo(() => buildFuelFeatures(stations), [stations])

  // Load drop images on mount
  useEffect(() => {
    if (!mapInstance?.isStyleLoaded()) {
      return
    }

    const imageIds = ["fuel-drop-available", "fuel-drop-unavailable"]
    const colors = [colorPalette.fuel.available, colorPalette.fuel.unavailable]

    imageIds.forEach((id, idx) => {
      if (!mapInstance.hasImage(id)) {
        const svgString = markerIcons.fuelDrop(colors[idx])
        const img = new Image()
        img.onload = () => {
          if (!mapInstance.hasImage(id)) {
            mapInstance.addImage(id, img)
          }
        }
        img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgString)}`
      }
    })
  }, [mapInstance])

  const buildLayers = useCallback((sourceId: string): LayerWithVisibility[] => {
    const layers = [
      // Cluster circles for x2-x3
      {
        id: CLUSTER_CIRCLE_LAYER_ID,
        type: "circle",
        source: sourceId,
        filter: ["has", "point_count"],
        shouldBeVisible: shouldShowClusters,
        paint: {
          "circle-color": colorPalette.fuel.available,
          "circle-radius": ["step", ["get", "point_count"], 18, 10, 20, 25, 22],
          "circle-opacity": 0.8,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
        },
      },
      // Cluster count text for x2-x3
      {
        id: CLUSTER_TEXT_LAYER_ID,
        type: "symbol",
        source: sourceId,
        filter: ["has", "point_count"],
        shouldBeVisible: shouldShowClusters,
        layout: {
          "text-field": "{point_count_abbreviated}",
          "text-size": 12,
          "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
        },
        paint: {
          "text-color": "#ffffff",
        },
      },
      // Individual drop markers from x2 and up
      {
        id: DROP_LAYER_ID,
        type: "symbol",
        source: sourceId,
        filter: ["!", ["has", "point_count"]],
        shouldBeVisible: shouldShowMapObjects,
        layout: {
          "icon-image": [
            "case",
            ["get", "truckAccessible"],
            "fuel-drop-available",
            "fuel-drop-unavailable",
          ],
          "icon-size": 1,
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
        },
      },
      // Labels only at x4 to keep x2-x3 clean
      {
        id: LABEL_LAYER_ID,
        type: "symbol",
        source: sourceId,
        filter: ["!", ["has", "point_count"]],
        shouldBeVisible: shouldShowObjectLabels,
        layout: {
          "text-field": ["coalesce", ["get", "brand"], ["get", "name"]],
          "text-size": 10,
          "text-offset": [0, 2.2],
          "text-anchor": "top",
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": "#166534",
          "text-halo-color": "#ffffff",
          "text-halo-width": 1,
        },
      },
    ]

    return layers as unknown as LayerWithVisibility[]
  }, [])

  useGeoJsonLayer({
    mapInstance,
    sourceId: SOURCE_ID,
    buildLayers,
    data,
    clusterOptions: {
      enabled: true,
      radius: 30,
      maxZoom: mapObjectZoom.clusterMax,
    },
  })

  return null
}
