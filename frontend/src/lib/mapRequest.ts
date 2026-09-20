import type { GeoJSONPoint, MapLayer, MapOverviewRequest } from "@/client"
import type { GeocodingSearchResponse } from "@/client/types.gen"

export type MapPointInput = { address: string } | { location: GeoJSONPoint }

export interface AddressSelection extends GeocodingSearchResponse {
  query: string
}

interface BuildRouteOverviewRequestOptions {
  pickup: MapPointInput
  delivery: MapPointInput
  radiusMeters?: number
  layers?: Array<MapLayer>
}

export function buildMapPointFromAddress(address: string): MapPointInput {
  return { address }
}

export function buildMapPointFromLocation(
  location: GeoJSONPoint,
): MapPointInput {
  return { location }
}

export function createAddressSelection(
  query: string,
  result: GeocodingSearchResponse,
): AddressSelection {
  return {
    query,
    formatted_address: result.formatted_address,
    location: result.location,
  }
}

export function buildRouteOverviewRequest({
  pickup,
  delivery,
  radiusMeters,
  layers,
}: BuildRouteOverviewRequestOptions): MapOverviewRequest {
  return {
    pickup,
    delivery,
    ...(radiusMeters !== undefined ? { radius_meters: radiusMeters } : {}),
    ...(layers ? { layers } : {}),
  }
}
