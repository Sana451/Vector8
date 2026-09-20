/**
 * Map API client
 *
 * Aggregated map overview combining routing, traffic, fuel stations and truck
 * restrictions in a single call.
 */

import {
  type GeocodingSearchResponse,
  GeocodingService,
  type MapOverviewRequest,
  type MapOverviewResponse,
  MapService,
} from "@/client"

/**
 * Fetch the aggregated map overview for a route.
 *
 * Optional layers degrade gracefully: on failure they come back empty and the
 * reason is listed in `errors`.
 *
 * @param request - Map overview request containing the route definition
 * @param forceRefresh - Skip caches and refresh from providers
 * @returns Aggregated map overview response
 * @throws AxiosError if the mandatory route layer fails
 */
export async function getRouteOverview(
  request: MapOverviewRequest,
  forceRefresh: boolean = false,
): Promise<MapOverviewResponse> {
  const response = await MapService.routeOverview({
    body: request,
    query: {
      force_refresh: forceRefresh,
    },
  })

  return response.data as MapOverviewResponse
}

export async function searchAddress(
  query: string,
  forceRefresh: boolean = false,
): Promise<GeocodingSearchResponse> {
  const response = await GeocodingService.search({
    body: { query },
    query: {
      force_refresh: forceRefresh,
    },
  })

  return response.data as GeocodingSearchResponse
}
