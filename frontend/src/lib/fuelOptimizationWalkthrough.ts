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

const METERS_PER_MILE = 1609.344

function segmentLengthMeters(a: Coordinate, b: Coordinate): number {
  return calculateRouteTotalDistanceMeters([a, b])
}

function lerpCoordinate(a: Coordinate, b: Coordinate, t: number): Coordinate {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
}

/**
 * Extract the part of the route between two distances (meters from start).
 */
export function sliceRouteByDistance(
  coordinates: Coordinate[],
  startMeters: number,
  endMeters: number,
): Coordinate[] {
  if (coordinates.length < 2 || endMeters <= startMeters) {
    return []
  }

  const result: Coordinate[] = []
  let traveled = 0

  for (let i = 0; i < coordinates.length - 1; i++) {
    const a = coordinates[i]
    const b = coordinates[i + 1]
    const segmentLength = segmentLengthMeters(a, b)
    const segmentStart = traveled
    const segmentEnd = traveled + segmentLength
    traveled = segmentEnd

    if (segmentEnd < startMeters) continue
    if (segmentStart > endMeters) break

    const t0 =
      segmentLength > 0
        ? Math.min(1, Math.max(0, (startMeters - segmentStart) / segmentLength))
        : 0
    const t1 =
      segmentLength > 0
        ? Math.min(1, Math.max(0, (endMeters - segmentStart) / segmentLength))
        : 1
    const p0 = lerpCoordinate(a, b, t0)
    const p1 = lerpCoordinate(a, b, t1)

    if (result.length === 0) result.push(p0)
    const last = result[result.length - 1]
    if (last[0] !== p1[0] || last[1] !== p1[1]) result.push(p1)
  }

  return result.length >= 2 ? result : []
}

/**
 * Route span reachable from a walkthrough step on the fuel it departs with.
 *
 * Uses the same fuel-to-distance conversion as the "Range on fuel" figure
 * in the walkthrough panel. `reserveStartMeters` marks where the reserve
 * begins: the span before it is covered on usable fuel, the span after it
 * on reserve. Returns null for steps without a departure (destination) or
 * when the range cannot be computed.
 */
export function getReachableRouteSegmentMeters(
  step: OptimizationStep,
  consumptionMpg: number,
  routeTotalDistanceMeters: number,
  reserveGallons = 0,
): {
  startMeters: number
  reserveStartMeters: number
  endMeters: number
} | null {
  if (step.kind === "destination" || !(consumptionMpg > 0)) {
    return null
  }

  const fuelOnDeparture =
    step.kind === "stop" ? step.fuelAfterGallons : step.fuelGallons
  if (fuelOnDeparture === undefined || Number.isNaN(fuelOnDeparture)) {
    return null
  }

  const metersPerGallon = consumptionMpg * METERS_PER_MILE
  const startMeters = step.routeOffsetMeters
  const endMeters = Math.min(
    routeTotalDistanceMeters,
    startMeters + Math.max(0, fuelOnDeparture) * metersPerGallon,
  )
  const reserveStartMeters = Math.min(
    endMeters,
    startMeters +
      Math.max(0, fuelOnDeparture - Math.max(0, reserveGallons)) *
        metersPerGallon,
  )

  return endMeters > startMeters
    ? { startMeters, reserveStartMeters, endMeters }
    : null
}

const DEFAULT_RESERVE_TANK_FRACTION = 0.1
const MIN_DEFAULT_RESERVE_GALLONS = 5
const MAX_DEFAULT_RESERVE_TANK_FRACTION = 0.25

/**
 * Suggested reserve fuel: 10% of the usable tank, at least 5 gal and at most
 * 25% of the tank. Returns null when the tank size is unknown.
 */
export function getDefaultReserveGallons(
  usableTankGallons: number,
): number | null {
  if (!(usableTankGallons > 0)) {
    return null
  }
  const suggested = Math.max(
    MIN_DEFAULT_RESERVE_GALLONS,
    Math.round(usableTankGallons * DEFAULT_RESERVE_TANK_FRACTION),
  )
  return Math.min(
    suggested,
    usableTankGallons * MAX_DEFAULT_RESERVE_TANK_FRACTION,
  )
}

export function getReserveLimits(
  usableTankGallons: number,
): { min: number; max: number } | null {
  if (!(usableTankGallons > 0)) {
    return null
  }
  const max = usableTankGallons * MAX_DEFAULT_RESERVE_TANK_FRACTION
  return { min: Math.min(MIN_DEFAULT_RESERVE_GALLONS, max), max }
}
