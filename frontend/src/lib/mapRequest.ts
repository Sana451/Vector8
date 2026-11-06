import type { GeoJSONPoint, MapLayer, MapOverviewRequest } from "@/client"
import type { GeocodingSearchResponse } from "@/client/types.gen"

export type MapPointInput =
  | { address: string }
  | { location: GeoJSONPoint; label?: string }

export interface AddressSelection extends GeocodingSearchResponse {
  query: string
}

interface BuildRouteOverviewRequestOptions {
  pickup: MapPointInput
  waypoint?: MapPointInput
  delivery: MapPointInput
  radiusMeters?: number
  layers?: Array<MapLayer>
  vehicleId?: string
  applyVehicleConstraints?: boolean
}

export function buildMapPointFromAddress(address: string): MapPointInput {
  return { address }
}

export function buildMapPointFromLocation(
  location: GeoJSONPoint,
  label?: string,
): MapPointInput {
  return label ? { location, label } : { location }
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
  waypoint,
  delivery,
  radiusMeters,
  layers,
  vehicleId,
  applyVehicleConstraints = true,
}: BuildRouteOverviewRequestOptions): MapOverviewRequest {
  return {
    pickup,
    ...(waypoint ? { waypoint } : {}),
    delivery,
    ...(radiusMeters !== undefined ? { radius_meters: radiusMeters } : {}),
    ...(layers ? { layers } : {}),
    ...(vehicleId && applyVehicleConstraints ? { vehicle_id: vehicleId } : {}),
  }
}
