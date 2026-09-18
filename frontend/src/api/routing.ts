/**
 * Routing API client
 *
 * Provides functions for calling the routing endpoints.
 */

import {
  type CalculateRouteRequest,
  type CalculateRouteResponse,
  RoutingService,
} from "@/client"

/**
 * Calculate route between origin and destination
 *
 * @param request - Route calculation request with origin and destination
 * @param forceRefresh - Skip cache and refresh from provider
 * @returns Route calculation response with coordinates
 * @throws AxiosError if request fails
 */
export async function calculateRoute(
  request: CalculateRouteRequest,
  forceRefresh: boolean = false,
): Promise<CalculateRouteResponse> {
  const response = await RoutingService.calculateRoute({
    body: request,
    query: {
      force_refresh: forceRefresh,
    },
  })

  return response.data as CalculateRouteResponse
}
