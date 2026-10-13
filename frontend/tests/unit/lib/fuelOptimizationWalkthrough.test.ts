import { describe, expect, it } from "vitest"
import type {
  FuelOptimizationCalculateResponse,
  FuelOptimizationItineraryPointPublic,
} from "@/client"
import {
  buildOptimizationSteps,
  getReachableRouteSegmentMeters,
  type OptimizationStep,
} from "@/lib/fuelOptimizationWalkthrough"

function makeItineraryPoint(
  overrides: Partial<FuelOptimizationItineraryPointPublic>,
): FuelOptimizationItineraryPointPublic {
  return {
    sequence: 0,
    kind: "start",
    status: "reached",
    label: "Start",
    route_offset_meters: "0",
    coordinate: ["-97", "40"],
    is_primary_failure_target: false,
    is_failure_point: false,
    ...overrides,
  }
}

function makeResponse(
  itinerary: FuelOptimizationItineraryPointPublic[],
): FuelOptimizationCalculateResponse {
  return {
    route_id: "route-id",
    vehicle_id: "vehicle-id",
    optimization_run_id: "run-id",
    status: "infeasible",
    algorithm: "greedy",
    algorithm_version: "1",
    summary: {
      total_fuel_consumed_gallons: "0",
      total_fuel_purchased_gallons: "0",
      total_fuel_cost: "0",
      total_detour_distance_meters: "0",
      total_detour_time_seconds: 0,
      number_of_stops: 0,
      remaining_fuel_gallons: "0",
    },
    stops: [],
    itinerary,
    failure: null,
    explanation: {
      summary: "Infeasible",
      outcome: "Destination cannot be reached.",
    },
  }
}

describe("buildOptimizationSteps", () => {
  it("includes destination as reached after the successful refuel sequence", () => {
    const response = makeResponse([
      makeItineraryPoint({ sequence: 0 }),
      makeItineraryPoint({
        sequence: 1,
        kind: "refuel",
        label: "Pilot",
        station_id: "station-id",
        route_offset_meters: "1000",
        coordinate: ["-96", "40"],
        fuel_before_gallons: "20",
        fuel_added_gallons: "30",
        fuel_after_gallons: "50",
      }),
      makeItineraryPoint({
        sequence: 2,
        kind: "destination",
        label: "Destination",
        route_offset_meters: "2000",
        coordinate: ["-95", "40"],
        fuel_gallons: "10",
      }),
    ])

    const steps = buildOptimizationSteps({
      response: { ...response, status: "success" },
      routeCoordinates: [
        [-97, 40],
        [-95, 40],
      ],
      fuelStations: [],
      initialFuelGallons: 30,
    })

    expect(steps.map((step) => [step.kind, step.status])).toEqual([
      ["start", "reached"],
      ["stop", "reached"],
      ["destination", "reached"],
    ])
    expect(steps[1].coordinate).toEqual([-96, 40])
    expect(steps[1].fuelAddedGallons).toBe(30)
    expect(steps[2].fuelGallons).toBe(10)
  })

  it("keeps reached refuels and shows only the primary unreachable target", () => {
    const response = makeResponse([
      makeItineraryPoint({
        sequence: 0,
        is_failure_point: false,
      }),
      makeItineraryPoint({
        sequence: 1,
        kind: "refuel",
        status: "reached",
        label: "Last station",
        station_id: "last-station",
        route_offset_meters: "1000",
        coordinate: ["-96", "40"],
      }),
      makeItineraryPoint({
        sequence: 2,
        kind: "unreachable_station",
        status: "unreachable",
        label: "Blocked station",
        station_id: "blocked-station",
        route_offset_meters: "1500",
        coordinate: ["-95.5", "40"],
        fuel_required_gallons: "15",
        available_fuel_gallons: "20",
        reserve_gallons: "10",
        deficit_gallons: "5",
        is_primary_failure_target: true,
      }),
      makeItineraryPoint({
        sequence: 3,
        kind: "destination",
        status: "unreachable",
        label: "Destination",
        route_offset_meters: "2000",
        coordinate: ["-95", "40"],
        fuel_required_gallons: "30",
        available_fuel_gallons: "20",
        reserve_gallons: "10",
        deficit_gallons: "20",
      }),
    ])

    const steps = buildOptimizationSteps({
      response,
      routeCoordinates: [
        [-97, 40],
        [-95, 40],
      ],
      fuelStations: [],
      initialFuelGallons: 30,
    })

    expect(steps.map((step: OptimizationStep) => step.status)).toEqual([
      "reached",
      "reached",
      "unreachable",
    ])
    expect(steps[1].stationId).toBe("last-station")
    expect(steps[2].isPrimaryFailureTarget).toBe(true)
    expect(steps[2].deficitGallons).toBe(5)
    expect(steps.map((step) => step.label)).not.toContain("Destination")
  })

  it("omits reached candidate stations that were not refueled", () => {
    const response = makeResponse([
      makeItineraryPoint({ sequence: 0 }),
      makeItineraryPoint({
        sequence: 1,
        kind: "station",
        label: "Passed without refueling",
        station_id: "pass-through-station",
        route_offset_meters: "500",
        coordinate: ["-96.5", "40"],
      }),
      makeItineraryPoint({
        sequence: 2,
        kind: "refuel",
        label: "Actual refuel",
        station_id: "refuel-station",
        route_offset_meters: "1000",
        coordinate: ["-96", "40"],
      }),
      makeItineraryPoint({
        sequence: 3,
        kind: "station",
        label: "Last reachable station",
        station_id: "last-reachable-station",
        route_offset_meters: "1500",
        coordinate: ["-95.5", "40"],
        is_failure_point: true,
      }),
    ])

    const steps = buildOptimizationSteps({
      response,
      routeCoordinates: [
        [-97, 40],
        [-95, 40],
      ],
      fuelStations: [],
      initialFuelGallons: 30,
    })

    expect(steps.map((step) => step.label)).toEqual([
      "Start",
      "Actual refuel",
      "Last reachable station",
    ])
    expect(steps[2].kind).toBe("checkpoint")
    expect(steps[2].isFailurePoint).toBe(true)
  })
})

describe("getReachableRouteSegmentMeters", () => {
  const METERS_PER_GALLON_AT_10_MPG = 10 * 1609.344
  const startStep = {
    kind: "start",
    status: "reached",
    index: 0,
    label: "Start",
    coordinate: [-97, 40],
    routeOffsetMeters: 1000,
    fuelGallons: 10,
  } as OptimizationStep

  it("splits the span into usable fuel and reserve", () => {
    const span = getReachableRouteSegmentMeters(startStep, 10, 1_000_000, 2)
    expect(span).not.toBeNull()
    expect(span?.startMeters).toBe(1000)
    expect(span?.reserveStartMeters).toBeCloseTo(
      1000 + 8 * METERS_PER_GALLON_AT_10_MPG,
      3,
    )
    expect(span?.endMeters).toBeCloseTo(
      1000 + 10 * METERS_PER_GALLON_AT_10_MPG,
      3,
    )
  })

  it("treats the whole span as reserve when fuel is at or below reserve", () => {
    const span = getReachableRouteSegmentMeters(startStep, 10, 1_000_000, 10)
    expect(span?.reserveStartMeters).toBe(span?.startMeters)
  })

  it("clips the reserve boundary to the route end", () => {
    const span = getReachableRouteSegmentMeters(startStep, 10, 50_000, 2)
    expect(span?.endMeters).toBe(50_000)
    expect(span?.reserveStartMeters).toBe(50_000)
  })

  it("returns null for destination steps", () => {
    const destination = {
      ...startStep,
      kind: "destination",
    } as OptimizationStep
    expect(
      getReachableRouteSegmentMeters(destination, 10, 1_000_000, 2),
    ).toBeNull()
  })
})
