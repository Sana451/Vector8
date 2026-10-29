/**
 * TripStopsLayer component
 *
 * Renders the frozen trip stops as numbered markers. Unlike the optimizer's
 * walkthrough layer this one has no notion of an active step: a saved trip is
 * read-only, so every stop is drawn the same way.
 */

import type { Feature, FeatureCollection } from "geojson"
import {
  type MapGeoJSONFeature,
  type MapLayerMouseEvent,
  type Map as MapLibreMap,
  Popup,
} from "maplibre-gl"
import { useCallback, useEffect, useMemo } from "react"

import type { TripPlanStopSnapshot } from "@/client"
import { syncMapImages } from "@/lib/mapImages"
import { colorPalette, markerIcons } from "@/lib/mapMarkerIcons"
import {
  formatTripDetour,
  isTankFullAfterRefuel,
  parseDecimal,
} from "@/lib/tripStopFormat"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

const SOURCE_ID = "trip-stops"
const CIRCLE_LAYER_ID = "trip-stops-circle"
const LABEL_LAYER_ID = "trip-stops-label"
const FUEL_LAYER_ID = "trip-stops-fuel"
const FUEL_BADGE_LAYER_ID = "trip-stops-fuel-badge"
const FUEL_LABEL_LAYER_ID = "trip-stops-fuel-label"
// Distance below the drop icon's anchor where the numbered badge is drawn.
const FUEL_BADGE_OFFSET_PX = 14
const FUEL_IMAGE_ID = "trip-stop-fuel-drop"

interface TripStopsLayerProps {
  mapInstance: MapLibreMap | null
  stops: TripPlanStopSnapshot[]
  usableTankGallons?: string | number | null
}

function markerLabel(stop: TripPlanStopSnapshot): string {
  if (stop.kind === "start") return "S"
  if (stop.kind === "destination") return "D"
  return String(stop.sequence)
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
}

function formatMoney(value: unknown): string {
  if (typeof value !== "string" || value === "") return "—"
  const amount = Number(value)
  return Number.isNaN(amount) ? value : `$${amount.toFixed(2)}`
}

function formatGallons(value: unknown): string {
  if (typeof value !== "string" || value === "") return "—"
  const gallons = Number(value)
  return Number.isNaN(gallons) ? value : `${gallons.toFixed(1)} gal`
}

function formatStationPrice(value: unknown, currency: unknown): string {
  if (typeof value !== "number") return "—"
  const code = typeof currency === "string" && currency ? currency : "USD"
  return `${value.toFixed(3)} ${code}`
}

function buildStationRows(station: Record<string, unknown>): string {
  const brand = String(station.brand ?? "")
  const name = String(station.name ?? "")
  const fuelType = String(station.fuel_type ?? "")
  const isOpen = station.is_open
  const status =
    typeof isOpen === "boolean"
      ? isOpen
        ? "Open now"
        : "Closed"
      : "Hours unavailable"
  const address = String(station.address ?? "")
  const phone = String(station.phone ?? "")
  const website = String(station.website ?? "")

  return [
    brand && brand !== name
      ? `<div><strong>Brand:</strong> ${escapeHtml(brand)}</div>`
      : "",
    fuelType ? `<div><strong>Fuel:</strong> ${escapeHtml(fuelType)}</div>` : "",
    `<div><strong>Price:</strong> ${escapeHtml(formatStationPrice(station.diesel_price, station.currency))}</div>`,
    `<div><strong>AdBlue:</strong> ${station.has_adblue === true ? "✓ Available" : "—"}</div>`,
    `<div><strong>Truck Access:</strong>
      <div style="margin-left: 16px;">
        <div>Medium trucks: ${station.medium_truck_accessible === true ? "✓ Yes" : "✗ No"}</div>
        <div>Large trucks: ${station.large_truck_accessible === true ? "✓ Yes" : "✗ No"}</div>
      </div>
    </div>`,
    `<div><strong>Status:</strong> ${escapeHtml(status)}</div>`,
    address
      ? `<div><strong>Address:</strong> ${escapeHtml(address)}</div>`
      : "",
    phone ? `<div><strong>Phone:</strong> ${escapeHtml(phone)}</div>` : "",
    website
      ? `<div><strong>Website:</strong> ${escapeHtml(website)}</div>`
      : "",
  ]
    .filter(Boolean)
    .join("")
}

function buildPopupHtml(properties: Record<string, unknown>): string {
  const label = escapeHtml(String(properties.label ?? "Fuel stop"))
  const station =
    typeof properties.station === "string" && properties.station !== ""
      ? (JSON.parse(properties.station) as Record<string, unknown>)
      : null
  const stationRows = station ? buildStationRows(station) : ""
  const fuelAdded = parseDecimal(properties.fuelAdded as string)
  const fuelAddedText =
    fuelAdded === null
      ? "—"
      : `<span style="color: #059669; font-weight: 600;">+${fuelAdded.toFixed(1)} gal</span>`
  const fuelAfterText = formatGallons(properties.fuelAfter)
  const isFull =
    properties.isFull === true
      ? ` <span style="color: #64748b;">(full)</span>`
      : ""
  const trip = [
    ["Fuel on arrival", formatGallons(properties.fuelBefore)],
    ["Fuel to add", fuelAddedText],
    ["Fuel after refuel", `${fuelAfterText}${isFull}`],
    ["Price per gallon", formatMoney(properties.fuelPrice)],
    ["Cost at this stop", formatMoney(properties.fuelCost)],
    [
      "Detour",
      formatTripDetour(
        properties.detourMeters as string,
        typeof properties.detourSeconds === "number"
          ? properties.detourSeconds
          : null,
      ),
    ],
  ]
    .map(
      ([title, value]) =>
        `<div><strong>${title}:</strong> ${value.startsWith("<") ? value : escapeHtml(value)}</div>`,
    )
    .join("")
  const rows = `${stationRows}<div style="margin-top: 8px; border-top: 1px dashed #a7f3d0; padding-top: 8px;">${trip}</div>`

  return `
    <div style="
      width: 240px;
      box-sizing: border-box;
      word-break: break-word;
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
      ">${label}</div>
      ${rows}
    </div>
  `
}

function buildFeatures(
  stops: TripPlanStopSnapshot[],
  usableTankGallons: string | number | null | undefined,
): FeatureCollection | null {
  if (stops.length === 0) {
    return null
  }

  const features: Feature[] = stops.map((stop) => ({
    type: "Feature",
    id: stop.sequence,
    properties: {
      kind: stop.kind,
      label: stop.label,
      markerLabel: markerLabel(stop),
      fuelBefore: stop.fuel_before_gallons ?? "",
      fuelAdded: stop.fuel_added_gallons ?? "",
      fuelAfter: stop.fuel_after_gallons ?? "",
      isFull: isTankFullAfterRefuel(stop.fuel_after_gallons, usableTankGallons),
      fuelPrice: stop.fuel_price_per_gallon ?? "",
      fuelCost: stop.fuel_cost ?? "",
      detourMeters: stop.detour_distance_meters ?? "",
      detourSeconds: stop.detour_time_seconds ?? null,
      station: stop.station ? JSON.stringify(stop.station) : "",
    },
    geometry: { type: "Point", coordinates: stop.coordinate },
  }))

  return { type: "FeatureCollection", features }
}

/**
 * Trip stop markers.
 *
 * Refuel stops use the same fuel-drop icon as the optimizer and open a popup
 * on click. Start and destination are drawn as coloured circles.
 *
 * @param mapInstance - MapLibre Map instance from the TomTom SDK
 * @param stops - Frozen stop snapshots in travel order
 */
export function TripStopsLayer({
  mapInstance,
  stops,
  usableTankGallons,
}: TripStopsLayerProps) {
  const data = useMemo(
    () => buildFeatures(stops, usableTankGallons),
    [stops, usableTankGallons],
  )

  const buildLayers = useCallback(
    (sourceId: string): LayerWithVisibility[] => [
      {
        id: CIRCLE_LAYER_ID,
        type: "circle",
        source: sourceId,
        filter: ["in", ["get", "kind"], ["literal", ["start", "destination"]]],
        paint: {
          "circle-radius": 12,
          "circle-color": [
            "match",
            ["get", "kind"],
            "start",
            "#16a34a",
            "#dc2626",
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      },
      {
        id: LABEL_LAYER_ID,
        type: "symbol",
        source: sourceId,
        filter: ["in", ["get", "kind"], ["literal", ["start", "destination"]]],
        layout: {
          "text-field": ["get", "markerLabel"],
          "text-size": 12,
          "text-allow-overlap": true,
        },
        paint: { "text-color": "#ffffff" },
      },
      {
        id: FUEL_LAYER_ID,
        type: "symbol",
        source: sourceId,
        filter: [
          "!",
          ["in", ["get", "kind"], ["literal", ["start", "destination"]]],
        ],
        layout: {
          "icon-image": FUEL_IMAGE_ID,
          "icon-size": 1,
          "icon-anchor": "bottom",
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
        },
      },
      {
        id: FUEL_BADGE_LAYER_ID,
        type: "circle",
        source: sourceId,
        filter: [
          "!",
          ["in", ["get", "kind"], ["literal", ["start", "destination"]]],
        ],
        paint: {
          "circle-radius": 10,
          "circle-color": "#16a34a",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
          "circle-opacity": 0.95,
          "circle-translate": [0, FUEL_BADGE_OFFSET_PX],
        },
      },
      {
        id: FUEL_LABEL_LAYER_ID,
        type: "symbol",
        source: sourceId,
        filter: [
          "!",
          ["in", ["get", "kind"], ["literal", ["start", "destination"]]],
        ],
        layout: {
          "text-field": ["get", "markerLabel"],
          "text-size": 12,
          "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
          "text-anchor": "center",
          "text-offset": [0, FUEL_BADGE_OFFSET_PX / 12],
          "text-allow-overlap": true,
          "text-ignore-placement": true,
        },
        paint: { "text-color": "#ffffff" },
      },
    ],
    [],
  )

  useGeoJsonLayer({ mapInstance, sourceId: SOURCE_ID, buildLayers, data })

  useEffect(() => {
    if (!mapInstance) {
      return
    }

    const disposeImages = syncMapImages(mapInstance, [
      {
        id: FUEL_IMAGE_ID,
        svg: markerIcons.fuelDrop(colorPalette.fuel.available),
      },
    ])

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
      popup?.remove()
      popup = new Popup({
        closeButton: true,
        closeOnClick: true,
        className: "fuel-station-popup",
      })
        .setLngLat([longitude, latitude])
        .setHTML(
          buildPopupHtml((feature.properties ?? {}) as Record<string, unknown>),
        )
        .addTo(mapInstance)
    }

    const onEnter = () => {
      mapInstance.getCanvas().style.cursor = "pointer"
    }
    const onLeave = () => {
      mapInstance.getCanvas().style.cursor = ""
    }

    const attach = () => {
      if (!mapInstance.getLayer(FUEL_LAYER_ID)) {
        return false
      }
      mapInstance.on("click", FUEL_LAYER_ID, showPopup)
      mapInstance.on("mouseenter", FUEL_LAYER_ID, onEnter)
      mapInstance.on("mouseleave", FUEL_LAYER_ID, onLeave)
      return true
    }

    let timer: ReturnType<typeof setTimeout> | undefined
    const scheduleAttach = () => {
      if (!attach()) {
        timer = setTimeout(scheduleAttach, 100)
      }
    }
    scheduleAttach()

    return () => {
      if (timer !== undefined) clearTimeout(timer)
      disposeImages()
      popup?.remove()
      if (mapInstance.getLayer(FUEL_LAYER_ID)) {
        mapInstance.off("click", FUEL_LAYER_ID, showPopup)
        mapInstance.off("mouseenter", FUEL_LAYER_ID, onEnter)
        mapInstance.off("mouseleave", FUEL_LAYER_ID, onLeave)
      }
    }
  }, [mapInstance])

  return null
}
