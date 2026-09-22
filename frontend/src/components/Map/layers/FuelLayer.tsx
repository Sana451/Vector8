/**
 * FuelLayer component
 *
 * Renders fuel stations as drop-shaped markers.
 * Shape = type (fuel drop), Color = availability
 */

import {
  type MapGeoJSONFeature,
  type MapLayerMouseEvent,
  type Map as MapLibreMap,
  Popup,
} from "maplibre-gl"
import { useCallback, useEffect, useMemo } from "react"
import type { FuelStationData } from "@/client"
import { syncMapImages } from "@/lib/mapImages"
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

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
}

function formatDistance(distanceMeters: unknown): string {
  if (typeof distanceMeters !== "number" || Number.isNaN(distanceMeters)) {
    return ""
  }
  if (distanceMeters >= 1609.344) {
    return `${(distanceMeters / 1609.344).toFixed(1)} mi`
  }
  return `${Math.round(distanceMeters).toLocaleString()} m`
}

function formatPrice(price: unknown, currency: unknown): string {
  if (typeof price !== "number" || Number.isNaN(price)) {
    return "Price unavailable"
  }
  const currencyCode =
    typeof currency === "string" && currency ? currency : "USD"
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currencyCode,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(price)
  } catch {
    return `${price.toFixed(2)} ${currencyCode}`
  }
}

function buildPopupHtml(properties: Record<string, unknown>): string {
  const name = escapeHtml(String(properties.name ?? "Fuel station"))
  const brand = escapeHtml(String(properties.brand ?? ""))
  const address = escapeHtml(String(properties.address ?? ""))
  const fuelType = escapeHtml(String(properties.fuelType ?? "Truck Diesel"))
  const price = escapeHtml(
    formatPrice(properties.dieselPrice, properties.currency),
  )
  const distance = escapeHtml(formatDistance(properties.distanceMeters))
  const hasAdblue = properties.hasAdblue === true
  const isOpen =
    typeof properties.isOpen === "boolean"
      ? properties.isOpen
        ? "Open now"
        : "Closed"
      : "Hours unavailable"
  const phone = escapeHtml(String(properties.phone ?? ""))
  const website = escapeHtml(String(properties.website ?? ""))
  const mediumTruckAccessible = properties.mediumTruckAccessible === true
  const largeTruckAccessible = properties.largeTruckAccessible === true

  const rows = [
    brand && brand !== name
      ? `<div><strong>Brand:</strong> ${brand}</div>`
      : "",
    fuelType ? `<div><strong>Fuel:</strong> ${fuelType}</div>` : "",
    `<div><strong>Price:</strong> ${price}</div>`,
    `<div><strong>AdBlue:</strong> ${hasAdblue ? "✓ Available" : "—"}</div>`,
    `<div><strong>Truck Access:</strong>
      <div style="margin-left: 16px;">
        <div>Medium trucks: ${mediumTruckAccessible ? "✓ Yes" : "✗ No"}</div>
        <div>Large trucks: ${largeTruckAccessible ? "✓ Yes" : "✗ No"}</div>
      </div>
    </div>`,
    distance ? `<div><strong>Distance:</strong> ${distance}</div>` : "",
    `<div><strong>Status:</strong> ${escapeHtml(isOpen)}</div>`,
    address ? `<div><strong>Address:</strong> ${address}</div>` : "",
    phone ? `<div><strong>Phone:</strong> ${phone}</div>` : "",
    website ? `<div><strong>Website:</strong> ${website}</div>` : "",
  ]
    .filter(Boolean)
    .join("")

  return `
    <div style="
      min-width: 280px;
      background: linear-gradient(135deg, #ecfdf5 0%, #ffffff 100%);
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
        color: #064e3b;
        border-bottom: 2px solid #a7f3d0;
        padding-bottom: 8px;
      ">
        ${name}
      </div>
      <div style="color: #334155;">
        ${rows}
      </div>
    </div>
  `
}

/**
 * Fuel station layer with drop markers.
 */
export function FuelLayer({ mapInstance, stations }: FuelLayerProps) {
  const data = useMemo(() => buildFuelFeatures(stations), [stations])

  // Load drop images on mount
  useEffect(() => {
    return syncMapImages(mapInstance, [
      {
        id: "fuel-drop-available",
        svg: markerIcons.fuelDrop(colorPalette.fuel.available),
      },
      {
        id: "fuel-drop-unavailable",
        svg: markerIcons.fuelDrop(colorPalette.fuel.unavailable),
      },
    ])
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
            ["all", ["get", "hasPriceData"], ["get", "largeTruckAccessible"]],
            "fuel-drop-available",
            "fuel-drop-unavailable",
          ],
          "icon-size": 1,
          "icon-anchor": "bottom",
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
        return
      }
      mapInstance.on("click", layerId, showPopup)
      mapInstance.on("mouseenter", layerId, onMouseEnter)
      mapInstance.on("mouseleave", layerId, onMouseLeave)
    }

    const timeoutId = setTimeout(() => {
      attachHandlers(DROP_LAYER_ID)
      attachHandlers(LABEL_LAYER_ID)
    }, 0)

    return () => {
      clearTimeout(timeoutId)
      popup?.remove()
      for (const layerId of [DROP_LAYER_ID, LABEL_LAYER_ID]) {
        if (mapInstance.getLayer(layerId)) {
          mapInstance.off("click", layerId, showPopup)
          mapInstance.off("mouseenter", layerId, onMouseEnter)
          mapInstance.off("mouseleave", layerId, onMouseLeave)
        }
      }
    }
  }, [mapInstance, data])

  return null
}
