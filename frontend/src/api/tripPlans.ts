/**
 * Trip plans API client
 *
 * A trip plan freezes an optimizer result and asks the routing provider for a
 * route that actually drives into every selected fuel stop.
 */

import {
  type TripPlanAssignRequest,
  type TripPlanCreateRequest,
  type TripPlanDetailPublic,
  type TripPlanExportFormat,
  type TripPlanRefineRequest,
  type TripPlanSharedPublic,
  type TripPlanSharePublic,
  type TripPlanStatus,
  type TripPlansPublic,
  TripPlansService,
} from "@/client"

/**
 * Save an optimizer result as a trip plan and refine its route.
 *
 * @throws AxiosError if the request fails
 */
export async function createTripPlan(
  request: TripPlanCreateRequest,
): Promise<TripPlanDetailPublic> {
  const response = await TripPlansService.plansCreateTripPlan({
    body: request,
  })

  return response.data as TripPlanDetailPublic
}

/**
 * Recalculate the refined route, e.g. after the optimizer changed.
 *
 * @throws AxiosError if the request fails
 */
export async function refineTripPlan(
  tripPlanId: string,
  request: TripPlanRefineRequest = {},
): Promise<TripPlanDetailPublic> {
  const response = await TripPlansService.plansRefineTripPlan({
    path: { trip_plan_id: tripPlanId },
    body: request,
  })

  return response.data as TripPlanDetailPublic
}

/**
 * Read a single trip plan with geometry, stops and deltas.
 *
 * @throws AxiosError if the request fails
 */
export async function readTripPlan(
  tripPlanId: string,
): Promise<TripPlanDetailPublic> {
  const response = await TripPlansService.plansReadTripPlan({
    path: { trip_plan_id: tripPlanId },
  })

  return response.data as TripPlanDetailPublic
}

/**
 * List trip plans owned by the current user.
 *
 * @throws AxiosError if the request fails
 */
export async function listTripPlans(
  skip = 0,
  limit = 100,
): Promise<TripPlansPublic> {
  const response = await TripPlansService.plansListTripPlans({
    query: { skip, limit },
  })

  return response.data as TripPlansPublic
}

/**
 * Delete a trip plan.
 *
 * @throws AxiosError if the request fails
 */
export async function deleteTripPlan(tripPlanId: string): Promise<void> {
  await TripPlansService.plansDeleteTripPlan({
    path: { trip_plan_id: tripPlanId },
  })
}

/**
 * List trip plans assigned to the signed-in driver.
 *
 * @throws AxiosError if the request fails
 */
export async function listMyTripPlans(
  skip = 0,
  limit = 100,
): Promise<TripPlansPublic> {
  const response = await TripPlansService.plansListMyTripPlans({
    query: { skip, limit },
  })

  return response.data as TripPlansPublic
}

/**
 * Assign a trip to a driver, or unassign it by passing `null`.
 *
 * @throws AxiosError if the request fails
 */
export async function assignTripPlan(
  tripPlanId: string,
  driverId: string | null,
): Promise<TripPlanDetailPublic> {
  const body: TripPlanAssignRequest = { driver_id: driverId }
  const response = await TripPlansService.plansAssignTripPlan({
    path: { trip_plan_id: tripPlanId },
    body,
  })

  return response.data as TripPlanDetailPublic
}

/**
 * Issue a public link for a trip, or revoke it with `enabled = false`.
 *
 * @returns the share token, or `null` once revoked
 * @throws AxiosError if the request fails
 */
export async function shareTripPlan(
  tripPlanId: string,
  enabled: boolean,
): Promise<string | null> {
  const response = await TripPlansService.plansShareTripPlan({
    path: { trip_plan_id: tripPlanId },
    body: { enabled },
  })

  return (response.data as TripPlanSharePublic).share_token ?? null
}

/**
 * Read a trip through its share token. Needs no account.
 *
 * @throws AxiosError if the token is unknown or revoked
 */
export async function readSharedTripPlan(
  shareToken: string,
): Promise<TripPlanSharedPublic> {
  const response = await TripPlansService.plansReadSharedTripPlan({
    path: { share_token: shareToken },
  })

  return response.data as TripPlanSharedPublic
}

/**
 * Move a trip along its lifecycle.
 *
 * @throws AxiosError if the request fails
 */
export async function updateTripPlanStatus(
  tripPlanId: string,
  status: TripPlanStatus,
): Promise<TripPlanDetailPublic> {
  const response = await TripPlansService.plansUpdateTripPlanStatus({
    path: { trip_plan_id: tripPlanId },
    body: { status },
  })

  return response.data as TripPlanDetailPublic
}

/**
 * Download a trip as GPX, KML or CSV and hand it to the browser.
 *
 * The blob is routed through an anchor click rather than a plain link because
 * the endpoint is authenticated and a bare `href` would not carry the token.
 *
 * @throws AxiosError if the request fails
 */
export async function downloadTripPlanExport(
  tripPlanId: string,
  exportFormat: TripPlanExportFormat,
  fileName: string,
): Promise<void> {
  const response = await TripPlansService.plansExportTripPlan({
    path: { trip_plan_id: tripPlanId, export_format: exportFormat },
  })

  const blob =
    response.data instanceof Blob
      ? response.data
      : new Blob([String(response.data)])
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = `${fileName}.${exportFormat}`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
