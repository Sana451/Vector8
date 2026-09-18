/**
 * Routing utilities
 *
 * Helper functions for working with route data.
 */

import type { CalculateRouteResponse } from "@/client"

export type Coordinate = [number, number]

/**
 * Extract route coordinates from API response
 *
 * Navigates through the response structure to extract the LineString
 * coordinates from the first route's first leg.
 *
 * Returns null if:
 * - routes array is empty
 * - first route has no legs
 * - first leg has no path
 * - coordinates array has less than 2 points
 *
 * @param response - Route calculation response from API
 * @returns Array of [longitude, latitude] coordinates or null if invalid
 */
export function extractRouteCoordinates(
  response: CalculateRouteResponse,
): Coordinate[] | null {
  // Check routes exist
  if (!response.routes || response.routes.length === 0) {
    return null
  }

  const firstRoute = response.routes[0]

  // Check legs exist
  if (!firstRoute.legs || firstRoute.legs.length === 0) {
    return null
  }

  const firstLeg = firstRoute.legs[0]

  // Check path exists
  if (!firstLeg.path) {
    return null
  }

  const { coordinates } = firstLeg.path

  // Check coordinates exist and have minimum 2 points
  if (!coordinates || coordinates.length < 2) {
    return null
  }

  return coordinates
}

/**
 * Calculate bounding box from coordinates
 *
 * Returns [minLon, minLat, maxLon, maxLat]
 *
 * @param coordinates - Array of [longitude, latitude] pairs
 * @returns Bounding box as [minLon, minLat, maxLon, maxLat]
 */
export function calculateBoundingBox(
  coordinates: Coordinate[],
): [number, number, number, number] {
  let minLon = coordinates[0][0]
  let maxLon = coordinates[0][0]
  let minLat = coordinates[0][1]
  let maxLat = coordinates[0][1]

  for (const [lon, lat] of coordinates) {
    if (lon < minLon) minLon = lon
    if (lon > maxLon) maxLon = lon
    if (lat < minLat) minLat = lat
    if (lat > maxLat) maxLat = lat
  }

  return [minLon, minLat, maxLon, maxLat]
}
