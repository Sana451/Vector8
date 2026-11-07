/**
 * Vehicles API client
 */

import {
  type VehiclePositionPublic,
  type VehiclePublic,
  VehiclesService,
} from "@/client"

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

/**
 * Fetch the last known position of every vehicle that has one
 *
 * @returns One position per vehicle
 * @throws Error if the request fails
 */
export async function listLatestVehiclePositions(): Promise<
  VehiclePositionPublic[]
> {
  const response = await VehiclesService.listLatestVehiclePositions()
  return response.data ?? []
}
