/**
 * OptimizationRejectedStationsLayer component
 *
 * Global toggle-able layer showing every fuel station that the optimizer
 * considered but skipped, colored by rejection reason, with a popup
 * explaining why. Points close to the currently active walkthrough step
 * (within the max allowed detour) are softly highlighted.
 */

import type { Feature, FeatureCollection } from "geojson"
import {
  type MapGeoJSONFeature,
  type MapLayerMouseEvent,
  type Map as MapLibreMap,
  Popup,
} from "maplibre-gl"
import { useCallback, useEffect, useMemo } from "react"
import type { FuelOptimizationSkippedStationStatPublic } from "@/client"
import {
  findNearbySkippedStationIds,
  type OptimizationStep,
} from "@/lib/fuelOptimizationWalkthrough"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "optimization-rejected-stations"
const CIRCLE_LAYER_ID = "optimization-rejected-stations-circle"

const REASON_COLORS: Record<string, string> = {
  duplicate_station_id: "#9ca3af",
  unsupported_fuel_type: "#64748b",
  missing_diesel_price: "#f59e0b",
  not_truck_accessible: "#a855f7",
  detour_distance_limit_exceeded: "#ef4444",
}
const DEFAULT_REASON_COLOR = "#6b7280"

interface OptimizationRejectedStationsLayerProps {
  mapInstance: MapLibreMap | null
  skippedStationStats: Array<FuelOptimizationSkippedStationStatPublic>
  activeStep: OptimizationStep | null
  maxAllowedDetourMeters: number | null
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
}

function buildRejectedFeatures(
  skippedStationStats: Array<FuelOptimizationSkippedStationStatPublic>,
  nearbyStationIds: Set<string>,
): FeatureCollection | null {
  const features: Feature[] = []

  for (const stat of skippedStationStats) {
    for (const point of stat.sample_points ?? []) {
      features.push({
        type: "Feature",
        id: point.station_id,
        properties: {
          stationId: point.station_id,
          name: point.name,
          reason: stat.reason,
          description: stat.description,
          isNear: nearbyStationIds.has(point.station_id),
        },
        geometry: {
          type: "Point",
          coordinates: [Number(point.longitude), Number(point.latitude)],
        },
      })
    }
  }

  return features.length > 0 ? { type: "FeatureCollection", features } : null
}

function buildPopupHtml(properties: Record<string, unknown>): string {
  const name = escapeHtml(String(properties.name ?? "Fuel station"))
  const description = escapeHtml(String(properties.description ?? ""))

  return `
    <div style="min-width: 220px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 13px; line-height: 1.5;">
      <div style="font-weight: 700; margin-bottom: 6px;">${name}</div>
      <div style="color: #b91c1c;">Rejected: ${description}</div>
    </div>
  `
}

/**
 * Rejected / skipped fuel stations, colored by rejection reason.
 */
export function OptimizationRejectedStationsLayer({
  mapInstance,
  skippedStationStats,
  activeStep,
  maxAllowedDetourMeters,
}: OptimizationRejectedStationsLayerProps) {
  const nearbyStationIds = useMemo(() => {
    const allPoints = skippedStationStats.flatMap(
      (stat) => stat.sample_points ?? [],
    )
    return findNearbySkippedStationIds(
      allPoints,
      activeStep,
      maxAllowedDetourMeters,
    )
  }, [skippedStationStats, activeStep, maxAllowedDetourMeters])

  const data = useMemo(
    () => buildRejectedFeatures(skippedStationStats, nearbyStationIds),
    [skippedStationStats, nearbyStationIds],
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
            ["get", "reason"],
            ...Object.entries(REASON_COLORS).flat(),
            DEFAULT_REASON_COLOR,
          ],
          "circle-radius": ["case", ["get", "isNear"], 9, 5],
          "circle-opacity": ["case", ["get", "isNear"], 0.95, 0.55],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": ["case", ["get", "isNear"], 2, 1],
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

  useEffect(() => {
    if (!mapInstance || !data) {
      return
    }

    let popup: Popup | null = null

    const showPopup = (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0] as MapGeoJSONFeature | undefined
      if (feature?.geometry.type !== "Point") {
        return
      }
      const [longitude, latitude] = feature.geometry.coordinates as [
        number,
        number,
      ]
      const properties = (feature.properties ?? {}) as Record<string, unknown>

      popup?.remove()
      popup = new Popup({ closeButton: true, closeOnClick: true })
        .setLngLat([longitude, latitude])
        .setHTML(buildPopupHtml(properties))
        .addTo(mapInstance)
    }

    const onMouseEnter = () => {
      mapInstance.getCanvas().style.cursor = "pointer"
    }
    const onMouseLeave = () => {
      mapInstance.getCanvas().style.cursor = ""
    }

    if (mapInstance.getLayer(CIRCLE_LAYER_ID)) {
      mapInstance.on("click", CIRCLE_LAYER_ID, showPopup)
      mapInstance.on("mouseenter", CIRCLE_LAYER_ID, onMouseEnter)
      mapInstance.on("mouseleave", CIRCLE_LAYER_ID, onMouseLeave)
    }

    return () => {
      popup?.remove()
      try {
        if (mapInstance.getLayer(CIRCLE_LAYER_ID)) {
          mapInstance.off("click", CIRCLE_LAYER_ID, showPopup)
          mapInstance.off("mouseenter", CIRCLE_LAYER_ID, onMouseEnter)
          mapInstance.off("mouseleave", CIRCLE_LAYER_ID, onMouseLeave)
        }
      } catch {
        // Layer may already be removed during teardown; ignore.
      }
    }
  }, [mapInstance, data])

  return null
}
