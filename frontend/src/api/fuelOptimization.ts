import {
  type FuelOptimizationCalculateRequest,
  type FuelOptimizationCalculateResponse,
  FuelOptimizationService,
} from "@/client"
import { client } from "@/client/client.gen"

export async function calculateFuelOptimization(
  request: FuelOptimizationCalculateRequest,
): Promise<FuelOptimizationCalculateResponse> {
  const response =
    await FuelOptimizationService.optimizationCalculateFuelOptimization({
      body: request,
    })

  return response.data as FuelOptimizationCalculateResponse
}

export interface FuelOptimizationChatMessage {
  role: "user" | "assistant"
  content: string
}

export interface FuelOptimizationExplainRequest {
  optimization: FuelOptimizationCalculateResponse
  stop_sequence?: number | null
  question?: string | null
  history?: FuelOptimizationChatMessage[]
  language?: "en" | "ru"
}

export interface FuelOptimizationExplainResponse {
  answer: string
  /** "fallback" means the AI was unavailable and a template answer was used. */
  source: "ai" | "fallback"
}

export async function explainFuelOptimization(
  request: FuelOptimizationExplainRequest,
): Promise<FuelOptimizationExplainResponse> {
  const response = await client.post<
    { 200: FuelOptimizationExplainResponse },
    unknown,
    true
  >({
    url: "/api/v1/fuel-optimization/explain",
    security: [{ scheme: "bearer", type: "http" }],
    body: request,
    headers: { "Content-Type": "application/json" },
  })

  return response.data as FuelOptimizationExplainResponse
}
