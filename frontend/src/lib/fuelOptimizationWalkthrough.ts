/**
 * Fuel optimization walkthrough helpers
 *
 * Builds the ordered reached/unreachable points for the walkthrough and map,
 * and computes proximity between skipped stations and the active step.
 */

import { lineString } from "@turf/helpers"
import { length } from "@turf/length"
import type {
  FuelOptimizationCalculateResponse,
  FuelOptimizationSkippedStationPointPublic,
  FuelStationData,
} from "@/client"
import type { Coordinate } from "@/lib/routing"

export type OptimizationStepKind =
  | "start"
  | "stop"
  | "destination"
  | "unreachable_station"
  | "checkpoint"
export type OptimizationStepStatus = "reached" | "unreachable"

export interface OptimizationStep {
  kind: OptimizationStepKind
  status: OptimizationStepStatus
  /** 0-based index within the steps array */
  index: number
  label: string
  coordinate: Coordinate
  routeOffsetMeters: number
  stationId?: string
  /** Fields only present for "stop" steps */
  fuelBeforeGallons?: number
  fuelAddedGallons?: number
  fuelAfterGallons?: number
  fuelPricePerGallon?: number
  fuelCost?: number
  detourDistanceMeters?: number
  detourTimeSeconds?: number
  /** Fields only present for "start" / "destination" steps */
  fuelGallons?: number
  fuelRequiredGallons?: number
  availableFuelGallons?: number
  reserveGallons?: number
  deficitGallons?: number
  isPrimaryFailureTarget?: boolean
  isFailurePoint?: boolean
}

interface BuildStepsParams {
  response: FuelOptimizationCalculateResponse
  routeCoordinates: Coordinate[]
  fuelStations: Array<FuelStationData>
  initialFuelGallons: number
}

/**
 * Compute total route distance in meters from route coordinates.
 */
export function calculateRouteTotalDistanceMeters(
  routeCoordinates: Coordinate[] | null,
): number {
  if (!routeCoordinates || routeCoordinates.length < 2) {
    return 0
  }
  try {
    return length(lineString(routeCoordinates), { units: "kilometers" }) * 1000
  } catch {
    return 0
  }
}

/**
 * Build the ordered walkthrough steps from the server itinerary.
 */
export function buildOptimizationSteps({
  response,
  routeCoordinates,
  fuelStations,
  initialFuelGallons,
}: BuildStepsParams): OptimizationStep[] {
  if (response.itinerary?.length) {
    return [...response.itinerary]
      .filter((point) =>
        point.status === "unreachable"
          ? point.is_primary_failure_target
          : point.kind !== "station" || point.is_failure_point,
      )
      .sort((a, b) => a.sequence - b.sequence)
      .map((point, index) => {
        const kind: OptimizationStepKind =
          point.kind === "start"
            ? "start"
            : point.kind === "destination"
              ? "destination"
              : point.kind === "station"
                ? "checkpoint"
                : point.status === "unreachable"
                  ? "unreachable_station"
                  : "stop"
        const step: OptimizationStep = {
          kind,
          status: point.status,
          index,
          label: point.label,
          coordinate: [
            Number(point.coordinate[0]),
            Number(point.coordinate[1]),
          ],
          routeOffsetMeters: Number(point.route_offset_meters),
          stationId: point.station_id ?? undefined,
          fuelGallons:
            point.fuel_gallons === null || point.fuel_gallons === undefined
              ? undefined
              : Number(point.fuel_gallons),
          fuelBeforeGallons:
            point.fuel_before_gallons === null ||
            point.fuel_before_gallons === undefined
              ? undefined
              : Number(point.fuel_before_gallons),
          fuelAddedGallons:
            point.fuel_added_gallons === null ||
            point.fuel_added_gallons === undefined
              ? undefined
              : Number(point.fuel_added_gallons),
          fuelAfterGallons:
            point.fuel_after_gallons === null ||
            point.fuel_after_gallons === undefined
              ? undefined
              : Number(point.fuel_after_gallons),
          fuelPricePerGallon:
            point.fuel_price_per_gallon === null ||
            point.fuel_price_per_gallon === undefined
              ? undefined
              : Number(point.fuel_price_per_gallon),
          fuelCost:
            point.fuel_cost === null || point.fuel_cost === undefined
              ? undefined
              : Number(point.fuel_cost),
          detourDistanceMeters:
            point.detour_distance_meters === null ||
            point.detour_distance_meters === undefined
              ? undefined
              : Number(point.detour_distance_meters),
          detourTimeSeconds:
            point.detour_time_seconds === null ||
            point.detour_time_seconds === undefined
              ? undefined
              : point.detour_time_seconds,
          fuelRequiredGallons:
            point.fuel_required_gallons === null ||
            point.fuel_required_gallons === undefined
              ? undefined
              : Number(point.fuel_required_gallons),
          availableFuelGallons:
            point.available_fuel_gallons === null ||
            point.available_fuel_gallons === undefined
              ? undefined
              : Number(point.available_fuel_gallons),
          reserveGallons:
            point.reserve_gallons === null ||
            point.reserve_gallons === undefined
              ? undefined
              : Number(point.reserve_gallons),
          deficitGallons:
            point.deficit_gallons === null ||
            point.deficit_gallons === undefined
              ? undefined
              : Number(point.deficit_gallons),
          isPrimaryFailureTarget: point.is_primary_failure_target,
          isFailurePoint: point.is_failure_point,
        }
        return step
      })
  }

  const stationsById = new Map(
    fuelStations
      .filter((station) => station.station_id)
      .map((station) => [station.station_id as string, station]),
  )

  const steps: OptimizationStep[] = []
  const startCoordinate = routeCoordinates[0]
  const destinationCoordinate = routeCoordinates[routeCoordinates.length - 1]

  if (startCoordinate) {
    steps.push({
      kind: "start",
      status: "reached",
      index: steps.length,
      label: "Start",
      coordinate: startCoordinate,
      routeOffsetMeters: 0,
      fuelGallons: initialFuelGallons,
    })
  }

  const orderedStops = [...response.stops].sort(
    (a, b) => a.sequence - b.sequence,
  )

  for (const stop of orderedStops) {
    const station = stationsById.get(stop.station_id)
    const coordinate = station
      ? (station.location.coordinates as Coordinate)
      : (startCoordinate ?? [0, 0])

    steps.push({
      kind: "stop",
      status: "reached",
      index: steps.length,
      label: station?.name ?? `Stop #${stop.sequence}`,
      coordinate,
      routeOffsetMeters: Number(stop.route_offset_meters),
      stationId: stop.station_id,
      fuelBeforeGallons: Number(stop.fuel_before_gallons),
      fuelAddedGallons: Number(stop.fuel_added_gallons),
      fuelAfterGallons: Number(stop.fuel_after_gallons),
      fuelPricePerGallon: Number(stop.fuel_price_per_gallon),
      fuelCost: Number(stop.fuel_cost),
      detourDistanceMeters: Number(stop.detour_distance_meters),
      detourTimeSeconds: stop.detour_time_seconds,
    })
  }

  if (destinationCoordinate) {
    const totalRouteDistanceMeters =
      calculateRouteTotalDistanceMeters(routeCoordinates)
    steps.push({
      kind: "destination",
      status: "reached",
      index: steps.length,
      label: "Destination",
      coordinate: destinationCoordinate,
      routeOffsetMeters: totalRouteDistanceMeters,
      fuelGallons: Number(response.summary.remaining_fuel_gallons),
    })
  }

  return steps
}

/**
 * Determine which skipped-station points are "near" the currently active
 * step, using the requested max allowed detour as the proximity threshold
 * (falling back to a sane default when the constraint was not supplied).
 */
export function findNearbySkippedStationIds(
  points: Array<FuelOptimizationSkippedStationPointPublic>,
  activeStep: OptimizationStep | null,
  maxAllowedDetourMeters: number | null,
): Set<string> {
  if (!activeStep) {
    return new Set()
  }

  const threshold = maxAllowedDetourMeters ?? 50_000
  const nearby = new Set<string>()

  for (const point of points) {
    const offset = Number(point.route_offset_meters)
    if (Math.abs(offset - activeStep.routeOffsetMeters) <= threshold) {
      nearby.add(point.station_id)
    }
  }

  return nearby
}
