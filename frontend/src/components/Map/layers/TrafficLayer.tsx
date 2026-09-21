/**
 * TrafficLayer component
 *
 * Renders traffic incidents as severity-sized triangles.
 * Shape = type (triangle warning), Color = severity level
 */

import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useEffect, useMemo } from "react"
import type { TrafficLayerData } from "@/client"
import { syncMapImages } from "@/lib/mapImages"
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
    return syncMapImages(mapInstance, [
      {
        id: "traffic-triangle-severe",
        svg: markerIcons.trafficTriangle(
          colorPalette.traffic.severe,
          markerSizes.traffic.severe,
        ),
      },
      {
        id: "traffic-triangle-major",
        svg: markerIcons.trafficTriangle(
          colorPalette.traffic.moderate,
          markerSizes.traffic.moderate,
        ),
      },
      {
        id: "traffic-triangle-moderate",
        svg: markerIcons.trafficTriangle(
          colorPalette.traffic.moderate,
          markerSizes.traffic.moderate,
        ),
      },
      {
        id: "traffic-triangle-minor",
        svg: markerIcons.trafficTriangle(
          colorPalette.traffic.minor,
          markerSizes.traffic.minor,
        ),
      },
    ])
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
