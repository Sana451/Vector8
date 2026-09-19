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
  TrafficLayerData,
  TruckRestrictionData,
} from "@/client"
import type { Coordinate } from "@/lib/routing"

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
        dieselPrice: station.diesel_price ?? null,
        truckAccessible: station.truck_accessible ?? true,
      },
      geometry: {
        type: "Point",
        coordinates: [...station.location.coordinates],
      },
    })),
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
