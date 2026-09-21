/**
 * TruckRestrictionLayer component
 *
 * Renders truck restrictions as octagon-shaped warning markers.
 * Shape = type (warning octagon), Icon = restriction type
 */

import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useEffect, useMemo } from "react"
import type { TruckRestrictionData } from "@/client"
import {
  mapObjectZoom,
  shouldShowClusters,
  shouldShowMapObjects,
} from "@/lib/mapLayerInteraction"
import { buildTruckRestrictionFeatures } from "@/lib/mapLayers"
import {
  colorPalette,
  markerIcons,
  restrictionIcons,
} from "@/lib/mapMarkerIcons"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "truck-restrictions"
const OCTAGON_LAYER_ID = "truck-restrictions-octagons"
const CLUSTER_CIRCLE_LAYER_ID = "truck-restrictions-cluster-circle"
const CLUSTER_TEXT_LAYER_ID = "truck-restrictions-cluster-text"

interface TruckRestrictionLayerProps {
  mapInstance: MapLibreMap | null
  restrictions: Array<TruckRestrictionData> | undefined
}

/**
 * Truck restriction layer with octagon markers.
 */
export function TruckRestrictionLayer({
  mapInstance,
  restrictions,
}: TruckRestrictionLayerProps) {
  const data = useMemo(
    () => buildTruckRestrictionFeatures(restrictions),
    [restrictions],
  )

  // Load octagon images on mount
  useEffect(() => {
    if (!mapInstance?.isStyleLoaded()) {
      return
    }

    const restrictionTypes = [
      {
        key: "weight",
        color: colorPalette.truckRestrictions.weight,
        icon: restrictionIcons.weight_limit,
      },
      {
        key: "height",
        color: colorPalette.truckRestrictions.height,
        icon: restrictionIcons.height_restriction,
      },
      {
        key: "noTrucks",
        color: colorPalette.truckRestrictions.noTrucks,
        icon: restrictionIcons.no_trucks,
      },
      {
        key: "other",
        color: colorPalette.truckRestrictions.other,
        icon: restrictionIcons.other,
      },
    ]

    restrictionTypes.forEach(({ key, color, icon }) => {
      const imageId = `restriction-octagon-${key}`
      if (!mapInstance.hasImage(imageId)) {
        const svgString = markerIcons.restrictionOctagon(color, icon)
        const img = new Image()
        img.onload = () => {
          if (!mapInstance.hasImage(imageId)) {
            mapInstance.addImage(imageId, img)
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
          "circle-color": colorPalette.truckRestrictions.weight,
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
      // Individual octagon markers from x2 and up
      {
        id: OCTAGON_LAYER_ID,
        type: "symbol",
        source: sourceId,
        filter: ["!", ["has", "point_count"]],
        shouldBeVisible: shouldShowMapObjects,
        layout: {
          "icon-image": [
            "match",
            ["get", "restrictionType"],
            "weight_limit",
            "restriction-octagon-weight",
            "bridge_height",
            "restriction-octagon-height",
            "no_trucks",
            "restriction-octagon-noTrucks",
            "restriction-octagon-other",
          ],
          "icon-size": 1,
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
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
