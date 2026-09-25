/**
 * Vehicles API client
 */

import { type VehiclePublic, VehiclesService } from "@/client"

/**
 * Fetch list of vehicles for the current user
 *
 * @returns List of vehicles
 * @throws Error if the request fails
 */
export async function listVehicles(): Promise<VehiclePublic[]> {
  const response = await VehiclesService.listVehicles()
  return response.data?.data ?? []
}
