/**
 * Fuel optimization walkthrough helpers
 *
 * Builds the step-by-step model (start -> stops -> destination) used by the
 * OptimizationWalkthrough panel and the related map layers, and computes
 * proximity between skipped stations and the currently active step so they
 * can be softly highlighted on the map.
 */

import { lineString } from "@turf/helpers"
import { length } from "@turf/length"
import type {
  FuelOptimizationCalculateResponse,
  FuelOptimizationSkippedStationPointPublic,
  FuelStationData,
} from "@/client"
import type { Coordinate } from "@/lib/routing"

export type OptimizationStepKind = "start" | "stop" | "destination"

export interface OptimizationStep {
  kind: OptimizationStepKind
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
 * Build the ordered list of walkthrough steps: start, each stop (in
 * sequence order), and the destination.
 */
export function buildOptimizationSteps({
  response,
  routeCoordinates,
  fuelStations,
  initialFuelGallons,
}: BuildStepsParams): OptimizationStep[] {
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
