/**
 * TrafficLayer component
 *
 * Renders traffic incidents as severity-sized triangles.
 * Shape = type (triangle warning), Color = severity level
 */

import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useEffect, useMemo } from "react"
import type { TrafficLayerData } from "@/client"
import { shouldShowMapObjects } from "@/lib/mapLayerInteraction"
import { buildTrafficFeatures } from "@/lib/mapLayers"
import { colorPalette, markerIcons, markerSizes } from "@/lib/mapMarkerIcons"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "traffic"
const LAYER_ID = "traffic-layer"

interface TrafficLayerProps {
  mapInstance: MapLibreMap | null
  traffic: TrafficLayerData | null | undefined
}

/**
 * Traffic layer with triangle markers.
 * Size represents severity: larger = more severe.
 */
export function TrafficLayer({ mapInstance, traffic }: TrafficLayerProps) {
  const data = useMemo(() => {
    const result = buildTrafficFeatures(traffic)
    console.log("[TrafficLayer] Data built:", {
      hasData: !!result,
      features: result && "features" in result ? result.features.length : 0,
      traffic: !!traffic,
      incidents: traffic?.incidents?.length ?? 0,
    })
    return result
  }, [traffic])

  // Load triangle images on mount
  useEffect(() => {
    if (!mapInstance?.isStyleLoaded()) {
      console.log("[TrafficLayer] Skipping image load: map not ready")
      return
    }

    console.log("[TrafficLayer] Starting to load marker images")

    // Load triangle marker images for each severity level
    const severities = [
      {
        key: "severe",
        size: markerSizes.traffic.severe,
        color: colorPalette.traffic.severe,
      },
      {
        key: "major",
        size: markerSizes.traffic.moderate,
        color: colorPalette.traffic.moderate,
      },
      {
        key: "moderate",
        size: markerSizes.traffic.moderate,
        color: colorPalette.traffic.moderate,
      },
      {
        key: "minor",
        size: markerSizes.traffic.minor,
        color: colorPalette.traffic.minor,
      },
    ]

    let _loadedCount = 0
    severities.forEach(({ key, size, color }) => {
      const imageId = `traffic-triangle-${key}`
      if (!mapInstance.hasImage(imageId)) {
        const svgString = markerIcons.trafficTriangle(color, size)
        const img = new Image()
        img.onload = () => {
          if (!mapInstance.hasImage(imageId)) {
            mapInstance.addImage(imageId, img)
            console.log(`[TrafficLayer] Loaded image: ${imageId}`)
            _loadedCount++
          }
        }
        img.onerror = () => {
          console.error(`[TrafficLayer] Failed to load image: ${imageId}`)
        }
        img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgString)}`
      } else {
        console.log(`[TrafficLayer] Image already exists: ${imageId}`)
      }
    })
  }, [mapInstance])

  const buildLayers = useCallback(
    (sourceId: string): LayerWithVisibility[] =>
      [
        {
          id: LAYER_ID,
          type: "symbol",
          source: sourceId,
          layout: {
            "icon-image": [
              "match",
              ["get", "severity"],
              "severe",
              "traffic-triangle-severe",
              "major",
              "traffic-triangle-major",
              "moderate",
              "traffic-triangle-moderate",
              "minor",
              "traffic-triangle-minor",
              "traffic-triangle-minor",
            ],
            "icon-size": 1,
            "icon-allow-overlap": true,
            "icon-ignore-placement": true,
          },
        },
      ] as LayerWithVisibility[],
    [],
  )

  // Show traffic everywhere except the farthest route-only view
  const shouldBeVisible = useCallback(shouldShowMapObjects, [])

  useGeoJsonLayer({
    mapInstance,
    sourceId: SOURCE_ID,
    buildLayers,
    data,
    shouldBeVisible,
  })

  return null
}
