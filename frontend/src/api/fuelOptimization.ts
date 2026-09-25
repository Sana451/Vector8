import {
  type FuelOptimizationCalculateRequest,
  type FuelOptimizationCalculateResponse,
  FuelOptimizationService,
} from "@/client"

export async function calculateFuelOptimization(
  request: FuelOptimizationCalculateRequest,
): Promise<FuelOptimizationCalculateResponse> {
  const response =
    await FuelOptimizationService.optimizationCalculateFuelOptimization({
      body: request,
    })

  return response.data as FuelOptimizationCalculateResponse
}
