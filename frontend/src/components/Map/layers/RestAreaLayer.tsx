/**
 * RestAreaLayer component
 *
 * Renders HERE rest areas as POI markers with popup details.
 */

import {
  type LayerSpecification,
  type MapGeoJSONFeature,
  type MapLayerMouseEvent,
  type Map as MapLibreMap,
  Popup,
} from "maplibre-gl"
import { useCallback, useEffect, useMemo } from "react"
import type { RestAreaFeatureCollection } from "@/client"
import { buildRestAreaFeatures } from "@/lib/mapLayers"
import { useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "rest-areas"
const CIRCLE_LAYER_ID = "rest-areas-layer"
const LABEL_LAYER_ID = "rest-areas-label"
const TRUCK_PARKING_CATEGORY_ID = "700-7900-0131"
const COMPLETE_REST_AREA_CATEGORY_ID = "400-4300-0199"

interface RestAreaLayerProps {
  mapInstance: MapLibreMap | null
  restAreas: RestAreaFeatureCollection | null | undefined
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
}

function joinPopupLines(value: unknown): string {
  if (typeof value === "string") {
    return value
  }
  if (Array.isArray(value)) {
    return value
      .filter((item): item is string => typeof item === "string")
      .join(", ")
  }
  return ""
}

function buildPopupHtml(properties: Record<string, unknown>): string {
  const title = escapeHtml(String(properties.title ?? "Rest area"))
  const addressLabel = escapeHtml(String(properties.addressLabel ?? ""))
  const categories = escapeHtml(joinPopupLines(properties.categoryLabels))
  const distanceMeters = properties.distanceMeters
  const distance =
    typeof distanceMeters === "number"
      ? `${Math.round(distanceMeters).toLocaleString()} m`
      : ""
  const contacts = escapeHtml(String(properties.contactsSummary ?? ""))
  const openingHours = escapeHtml(String(properties.openingHoursSummary ?? ""))

  const rows = [
    addressLabel ? `<div><strong>Address:</strong> ${addressLabel}</div>` : "",
    categories ? `<div><strong>Categories:</strong> ${categories}</div>` : "",
    distance
      ? `<div><strong>Distance:</strong> ${escapeHtml(distance)}</div>`
      : "",
    openingHours
      ? `<div><strong>Opening hours:</strong> ${openingHours}</div>`
      : "",
    contacts ? `<div><strong>Contacts:</strong> ${contacts}</div>` : "",
  ]
    .filter(Boolean)
    .join("")

  return `<div style="min-width:240px"><div style="font-weight:600;margin-bottom:6px">${title}</div>${rows}</div>`
}

/**
 * Rest area POI layer.
 */
export function RestAreaLayer({ mapInstance, restAreas }: RestAreaLayerProps) {
  const data = useMemo(() => buildRestAreaFeatures(restAreas), [restAreas])

  useEffect(() => {
    if (!restAreas) {
      return
    }

    console.info("[HERE] RestAreaLayer received backend payload", {
      backendFeatures: restAreas.features?.length ?? 0,
      renderableFeatures:
        data && "features" in data && Array.isArray(data.features)
          ? data.features.length
          : 0,
    })
  }, [restAreas, data])

  const buildLayers = useCallback(
    (sourceId: string): LayerSpecification[] => [
      {
        id: CIRCLE_LAYER_ID,
        type: "circle",
        source: sourceId,
        paint: {
          "circle-radius": 7,
          "circle-color": [
            "match",
            ["get", "primaryCategoryId"],
            COMPLETE_REST_AREA_CATEGORY_ID,
            "#d97706",
            TRUCK_PARKING_CATEGORY_ID,
            "#2563eb",
            "#475569",
          ],
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#ffffff",
        },
      },
      {
        id: LABEL_LAYER_ID,
        type: "symbol",
        source: sourceId,
        layout: {
          "text-field": [
            "coalesce",
            ["get", "title"],
            ["get", "providerPlaceId"],
            "Rest area",
          ],
          "text-size": 10,
          "text-offset": [0, 1.4],
          "text-anchor": "top",
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": "#1e293b",
          "text-halo-color": "#ffffff",
          "text-halo-width": 1,
        },
      },
    ],
    [],
  )

  useGeoJsonLayer({ mapInstance, sourceId: SOURCE_ID, buildLayers, data })

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

    const attachHandlers = (layerId: string) => {
      if (!mapInstance.getLayer(layerId)) {
        return
      }
      mapInstance.on("click", layerId, showPopup)
      mapInstance.on("mouseenter", layerId, onMouseEnter)
      mapInstance.on("mouseleave", layerId, onMouseLeave)
    }

    attachHandlers(CIRCLE_LAYER_ID)
    attachHandlers(LABEL_LAYER_ID)

    return () => {
      popup?.remove()
      if (mapInstance.getLayer(CIRCLE_LAYER_ID)) {
        mapInstance.off("click", CIRCLE_LAYER_ID, showPopup)
        mapInstance.off("mouseenter", CIRCLE_LAYER_ID, onMouseEnter)
        mapInstance.off("mouseleave", CIRCLE_LAYER_ID, onMouseLeave)
      }
      if (mapInstance.getLayer(LABEL_LAYER_ID)) {
        mapInstance.off("click", LABEL_LAYER_ID, showPopup)
        mapInstance.off("mouseenter", LABEL_LAYER_ID, onMouseEnter)
        mapInstance.off("mouseleave", LABEL_LAYER_ID, onMouseLeave)
      }
    }
  }, [mapInstance, data])

  return null
}
