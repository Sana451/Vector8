/**
 * Map layer helpers
 *
 * Converts aggregated map overview payloads into GeoJSON suitable for
 * MapLibre sources. Each layer stays independent: a missing or failed layer
 * simply yields null.
 */

import type { Feature, FeatureCollection } from "geojson"
import type {
  FuelStationData,
  MapOverviewResponse,
  RestAreaFeatureCollection,
  TrafficLayerData,
  TruckRestrictionData,
} from "@/client"
import type { Coordinate } from "@/lib/routing"

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function isFiniteCoordinatePair(value: unknown): value is [number, number] {
  return (
    Array.isArray(value) &&
    value.length === 2 &&
    typeof value[0] === "number" &&
    Number.isFinite(value[0]) &&
    typeof value[1] === "number" &&
    Number.isFinite(value[1])
  )
}

function logRestAreaDebug(
  level: "info" | "warn",
  message: string,
  payload: Record<string, unknown>,
): void {
  const logger = level === "warn" ? console.warn : console.info
  logger(`[HERE] ${message}`, payload)
}

/**
 * Build a LineString feature from route coordinates.
 *
 * @param coordinates - Array of [longitude, latitude] pairs
 * @returns GeoJSON Feature or null when there are fewer than 2 points
 */
export function buildRouteFeature(
  coordinates: Coordinate[] | null,
): Feature | null {
  if (!coordinates || coordinates.length < 2) {
    return null
  }

  return {
    type: "Feature",
    properties: {},
    geometry: { type: "LineString", coordinates },
  }
}

/**
 * Build a point FeatureCollection for fuel stations.
 *
 * @param stations - Fuel stations from the map overview response
 * @returns GeoJSON FeatureCollection or null when there are no stations
 */
export function buildFuelFeatures(
  stations: Array<FuelStationData> | undefined,
): FeatureCollection | null {
  if (!stations || stations.length === 0) {
    return null
  }

  return {
    type: "FeatureCollection",
    features: stations.map((station) => ({
      type: "Feature",
      properties: {
        id: station.external_id,
        name: station.name,
        brand: station.brand ?? "",
        address: station.address ?? "",
        dieselPrice: station.diesel_price ?? null,
        currency: station.currency ?? null,
        fuelType: station.fuel_type ?? null,
        distanceMeters: station.distance_meters ?? null,
        isOpen: station.is_open ?? null,
        openingHours: station.opening_hours ?? [],
        phone: station.phone ?? null,
        website: station.website ?? null,
        hasAdblue: station.has_adblue ?? false,
        truckAccessible: station.truck_accessible ?? true,
      },
      geometry: {
        type: "Point",
        coordinates: [...station.location.coordinates],
      },
    })),
  }
}

function formatContactSummary(
  contacts: Array<Record<string, unknown>>,
): string {
  const values: string[] = []

  for (const contact of contacts) {
    for (const rawEntries of Object.values(contact)) {
      if (!Array.isArray(rawEntries)) {
        continue
      }
      for (const entry of rawEntries) {
        if (
          entry &&
          typeof entry === "object" &&
          "value" in entry &&
          typeof entry.value === "string"
        ) {
          values.push(entry.value)
        }
      }
    }
  }

  return values.join(", ")
}

function formatOpeningHoursSummary(
  openingHours: Array<Record<string, unknown>>,
): string {
  const values: string[] = []

  for (const entry of openingHours) {
    const text = entry.text
    if (Array.isArray(text)) {
      for (const line of text) {
        if (typeof line === "string") {
          values.push(line)
        }
      }
    }
  }

  return values.join(" | ")
}

function formatCategorySummary(
  categories: Array<Record<string, unknown>>,
): string {
  return categories
    .map((category) =>
      typeof category.name === "string"
        ? category.name
        : typeof category.id === "string"
          ? category.id
          : "unknown",
    )
    .join(", ")
}

/**
 * Build a point FeatureCollection for rest areas.
 *
 * The backend already returns GeoJSON, but this helper augments marker-friendly
 * properties such as primaryCategoryId and popup summaries.
 */
export function buildRestAreaFeatures(
  restAreas: RestAreaFeatureCollection | null | undefined,
): FeatureCollection | null {
  const backendFeatures = Array.isArray(restAreas?.features)
    ? restAreas.features
    : []

  if (backendFeatures.length === 0) {
    return null
  }

  const features: Feature[] = []

  for (const [index, feature] of backendFeatures.entries()) {
    const coordinates = feature.geometry?.coordinates
    if (!isFiniteCoordinatePair(coordinates)) {
      logRestAreaDebug("warn", "Skipping rest area with invalid coordinates", {
        featureId: feature.id,
        index,
        coordinates,
      })
      continue
    }

    const properties = isRecord(feature.properties) ? feature.properties : null
    if (
      !properties ||
      typeof properties.provider !== "string" ||
      typeof properties.provider_place_id !== "string" ||
      typeof properties.title !== "string"
    ) {
      logRestAreaDebug("warn", "Skipping rest area with invalid properties", {
        featureId: feature.id,
        index,
        properties,
      })
      continue
    }

    const categories = Array.isArray(properties.categories)
      ? properties.categories.filter(isRecord)
      : []
    const primaryCategory =
      categories.find((category) => category.primary === true) ??
      categories[0] ??
      null
    const address = isRecord(properties.address) ? properties.address : null
    const contacts = Array.isArray(properties.contacts)
      ? properties.contacts.filter(isRecord)
      : []
    const openingHours = Array.isArray(properties.opening_hours)
      ? properties.opening_hours.filter(isRecord)
      : []
    const categoryIds = categories
      .map((category) => (typeof category.id === "string" ? category.id : ""))
      .filter((categoryId) => categoryId.length > 0)
    const categoryLabels = formatCategorySummary(categories)
    const openingHoursSummary = formatOpeningHoursSummary(openingHours)
    const contactsSummary = formatContactSummary(contacts)

    features.push({
      type: "Feature",
      id: feature.id,
      properties: {
        id: feature.id,
        provider: properties.provider,
        providerPlaceId: properties.provider_place_id,
        title: properties.title,
        resultType:
          typeof properties.result_type === "string"
            ? properties.result_type
            : null,
        categoryIds: categoryIds.join(","),
        categoryLabels,
        primaryCategoryId:
          primaryCategory && typeof primaryCategory.id === "string"
            ? primaryCategory.id
            : null,
        distanceMeters:
          typeof properties.distance_meters === "number"
            ? properties.distance_meters
            : null,
        addressLabel: typeof address?.label === "string" ? address.label : "",
        openingHoursSummary,
        contactsSummary,
      },
      geometry: {
        type: "Point",
        coordinates: [...coordinates],
      },
    })
  }

  if (features.length === 0) {
    logRestAreaDebug("warn", "Rest area payload had no renderable features", {
      received: backendFeatures.length,
    })
    return null
  }

  logRestAreaDebug("info", "Prepared rest area features for rendering", {
    received: backendFeatures.length,
    renderable: features.length,
  })

  return {
    type: "FeatureCollection",
    features,
  }
}

/**
 * Build a point FeatureCollection for truck restrictions.
 *
 * @param restrictions - Truck restrictions from the map overview response
 * @returns GeoJSON FeatureCollection or null when there are no restrictions
 */
export function buildTruckRestrictionFeatures(
  restrictions: Array<TruckRestrictionData> | undefined,
): FeatureCollection | null {
  if (!restrictions || restrictions.length === 0) {
    return null
  }

  return {
    type: "FeatureCollection",
    features: restrictions.map((restriction) => ({
      type: "Feature",
      properties: {
        id: restriction.external_id,
        restrictionType: restriction.restriction_type ?? "other",
        description: restriction.description ?? "",
        maxHeightCm: restriction.max_height_cm ?? null,
        maxWeightKg: restriction.max_weight_kg ?? null,
      },
      geometry: {
        type: "Point",
        coordinates: [...restriction.location.coordinates],
      },
    })),
  }
}

/**
 * Build a point FeatureCollection for traffic incidents.
 *
 * Incidents without a location are skipped.
 *
 * @param traffic - Traffic layer payload from the map overview response
 * @returns GeoJSON FeatureCollection or null when there are no incidents
 */
export function buildTrafficFeatures(
  traffic: TrafficLayerData | null | undefined,
): FeatureCollection | null {
  const incidents = traffic?.incidents

  if (!incidents || incidents.length === 0) {
    return null
  }

  const features: Feature[] = []

  for (const incident of incidents) {
    if (!incident.location) {
      continue
    }

    features.push({
      type: "Feature",
      properties: {
        id: incident.external_id ?? "",
        severity: incident.severity ?? "unknown",
        category: incident.category ?? "",
        description: incident.description ?? "",
        delaySeconds: incident.delay_seconds ?? null,
      },
      geometry: {
        type: "Point",
        coordinates: [...incident.location.coordinates],
      },
    })
  }

  return features.length > 0 ? { type: "FeatureCollection", features } : null
}

/**
 * Extract route coordinates from an aggregated map overview response.
 *
 * Concatenates the geometry of every leg of the first route.
 *
 * @param response - Map overview response
 * @returns Array of [longitude, latitude] pairs or null when unavailable
 */
export function extractOverviewCoordinates(
  response: MapOverviewResponse,
): Coordinate[] | null {
  const routes = response.route?.routes

  if (!routes || routes.length === 0) {
    return null
  }

  const coordinates: Coordinate[] = []

  for (const leg of routes[0].legs ?? []) {
    if (leg.path?.coordinates) {
      coordinates.push(...leg.path.coordinates)
    }
  }

  return coordinates.length >= 2 ? coordinates : null
}
