/**
 * Drivers API client
 *
 * Drivers are the users a dispatcher assigns trips to; their profile holds
 * the contact and licence details that never belong on a trip itself.
 */

import {
  type DriverProfilePublic,
  type DriverProfileUpdate,
  type DriverPublic,
  type DriversPublic,
  DriversService,
} from "@/client"

/**
 * List drivers available for assignment.
 *
 * @throws AxiosError if the request fails
 */
export async function listDrivers(
  skip = 0,
  limit = 100,
): Promise<DriversPublic> {
  const response = await DriversService.listDrivers({
    query: { skip, limit },
  })

  return response.data as DriversPublic
}

/**
 * Read the signed-in driver's own profile.
 *
 * @throws AxiosError if the request fails
 */
export async function readOwnDriverProfile(): Promise<DriverProfilePublic> {
  const response = await DriversService.readOwnProfile()

  return response.data as DriverProfilePublic
}

/**
 * Update the signed-in driver's own profile.
 *
 * @throws AxiosError if the request fails
 */
export async function updateOwnDriverProfile(
  profile: DriverProfileUpdate,
): Promise<DriverProfilePublic> {
  const response = await DriversService.updateOwnProfile({ body: profile })

  return response.data as DriverProfilePublic
}

/**
 * Update a driver's profile as a dispatcher.
 *
 * @throws AxiosError if the request fails
 */
export async function updateDriverProfile(
  userId: string,
  profile: DriverProfileUpdate,
): Promise<DriverPublic> {
  const response = await DriversService.updateDriverProfile({
    path: { user_id: userId },
    body: profile,
  })

  return response.data as DriverPublic
}
