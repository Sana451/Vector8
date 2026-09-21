/**
 * RestAreaLayer component
 *
 * Renders HERE rest areas as POI markers with popup details.
 */

import {
  type MapGeoJSONFeature,
  type MapLayerMouseEvent,
  type Map as MapLibreMap,
  Popup,
} from "maplibre-gl"
import { useCallback, useEffect, useMemo } from "react"
import type { RestAreaFeatureCollection } from "@/client"
import {
  mapObjectZoom,
  shouldShowClusters,
  shouldShowMapObjects,
  shouldShowObjectLabels,
} from "@/lib/mapLayerInteraction"
import { buildRestAreaFeatures } from "@/lib/mapLayers"
import { colorPalette, markerIcons, restAreaIcons } from "@/lib/mapMarkerIcons"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "vector8-rest-areas-source"
const CIRCLE_LAYER_ID = "vector8-rest-areas-circle-layer"
const LABEL_LAYER_ID = "vector8-rest-areas-label-layer"
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

  return `
    <div style="
      min-width: 280px;
      background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
      border-radius: 8px;
      padding: 12px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      color: #1e293b;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px;
      line-height: 1.5;
    ">
      <div style="
        font-weight: 700;
        margin-bottom: 10px;
        font-size: 16px;
        color: #0f172a;
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 8px;
      ">
        ${title}
      </div>
      <div style="
        color: #334155;
      ">
        ${rows}
      </div>
    </div>
  `
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

    // Log all unique primary categories found in the data
    const categories = new Set<string | null>()
    restAreas.features?.forEach((feature) => {
      const props = feature.properties as any
      categories.add(props?.primaryCategoryId ?? null)
    })

    console.info("[HERE] RestAreaLayer received backend payload", {
      backendFeatures: restAreas.features?.length ?? 0,
      renderableFeatures:
        data && "features" in data && Array.isArray(data.features)
          ? data.features.length
          : 0,
      uniquePrimaryCategories: Array.from(categories),
    })
  }, [restAreas, data])

  // Load square marker images on mount
  useEffect(() => {
    if (!mapInstance?.isStyleLoaded()) {
      return
    }

    const restAreaTypes = [
      {
        key: "complete",
        categoryId: COMPLETE_REST_AREA_CATEGORY_ID,
        color: colorPalette.restAreas.complete,
        icon: restAreaIcons["400-4300-0199"],
      },
      {
        key: "parking",
        categoryId: TRUCK_PARKING_CATEGORY_ID,
        color: colorPalette.restAreas.parking,
        icon: restAreaIcons["700-7900-0131"],
      },
      {
        key: "other",
        categoryId: null,
        color: colorPalette.restAreas.stop,
        icon: restAreaIcons.default,
      },
    ]

    restAreaTypes.forEach(({ key, color, icon }) => {
      const imageId = `rest-area-square-${key}`
      if (!mapInstance.hasImage(imageId)) {
        const svgString = markerIcons.restAreaSquare(color, icon)
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
        id: "rest-areas-cluster-circle",
        type: "circle",
        source: sourceId,
        filter: ["has", "point_count"],
        shouldBeVisible: shouldShowClusters,
        paint: {
          "circle-color": colorPalette.restAreas.complete,
          "circle-radius": ["step", ["get", "point_count"], 18, 10, 20, 25, 22],
          "circle-opacity": 0.8,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
        },
      },
      // Cluster count text for x2-x3
      {
        id: "rest-areas-cluster-text",
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
      // Individual markers from x2 and up
      {
        id: CIRCLE_LAYER_ID,
        type: "symbol",
        source: sourceId,
        filter: ["!", ["has", "point_count"]],
        shouldBeVisible: shouldShowMapObjects,
        layout: {
          "icon-image": [
            "match",
            ["get", "primaryCategoryId"],
            COMPLETE_REST_AREA_CATEGORY_ID,
            "rest-area-square-complete",
            TRUCK_PARKING_CATEGORY_ID,
            "rest-area-square-parking",
            "rest-area-square-other",
          ],
          "icon-size": 1.2,
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
          "text-field": [
            "coalesce",
            ["get", "title"],
            ["get", "providerPlaceId"],
            "Rest area",
          ],
          "text-size": 10,
          "text-offset": [0, 2.2],
          "text-anchor": "top",
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": "#1e293b",
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
      const layer = mapInstance.getLayer(layerId)
      if (!layer) {
        console.warn(`[RestAreaLayer] Layer not found: ${layerId}`)
        return
      }
      console.info(`[RestAreaLayer] Attaching handlers to layer: ${layerId}`)
      mapInstance.on("click", layerId, showPopup)
      mapInstance.on("mouseenter", layerId, onMouseEnter)
      mapInstance.on("mouseleave", layerId, onMouseLeave)
    }

    // Use setTimeout to ensure layers are added to the map first
    const timeoutId = setTimeout(() => {
      attachHandlers(CIRCLE_LAYER_ID)
    }, 0)

    return () => {
      clearTimeout(timeoutId)
      popup?.remove()
      if (mapInstance.getLayer(CIRCLE_LAYER_ID)) {
        mapInstance.off("click", CIRCLE_LAYER_ID, showPopup)
        mapInstance.off("mouseenter", CIRCLE_LAYER_ID, onMouseEnter)
        mapInstance.off("mouseleave", CIRCLE_LAYER_ID, onMouseLeave)
      }
    }
  }, [mapInstance, data])

  return null
}
