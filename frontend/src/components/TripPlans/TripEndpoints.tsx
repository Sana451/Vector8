import type { ReactNode } from "react"

import type { TripPlanDetailPublic } from "@/client"
import { formatMiles } from "@/lib/tripPlans"
import {
  formatTripGallons,
  formatTripMoney,
  parseDecimal,
} from "@/lib/tripStopFormat"

type Props = {
  trip: Pick<
    TripPlanDetailPublic,
    "stops" | "base_distance_meters" | "refined_distance_meters"
  >
}

type StopLike = NonNullable<TripPlanDetailPublic["stops"]>[number]

export function getStopDistances(
  stops: StopLike[],
  routeTotal: number,
): { toNext: number | null; toDestination: number | null }[] {
  return stops.map((stop, index) => {
    const offset = parseDecimal(stop.route_offset_meters ?? null)
    const nextOffset =
      index + 1 < stops.length
        ? parseDecimal(stops[index + 1].route_offset_meters ?? null)
        : null
    return {
      toNext:
        offset !== null && nextOffset !== null ? nextOffset - offset : null,
      toDestination: offset !== null ? routeTotal - offset : null,
    }
  })
}

export function formatStopDistance(meters: number | null): string {
  return meters === null ? "—" : formatMiles(meters)
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">{value}</span>
    </div>
  )
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="vector8-surface p-4 space-y-2 text-sm">
      <p className="vector8-kicker">{title}</p>
      {children}
    </div>
  )
}

export function TripEndpoints({ trip }: Props) {
  const stops = trip.stops ?? []
  const start = stops.find((stop) => stop.kind === "start") ?? stops[0]
  const destination =
    stops.find((stop) => stop.kind === "destination") ?? stops[stops.length - 1]
  const nextStop =
    start === undefined
      ? undefined
      : stops.find((stop) => stop.sequence === start.sequence + 1)

  const routeTotal = trip.refined_distance_meters ?? trip.base_distance_meters
  const startOffset = parseDecimal(start?.route_offset_meters ?? null)
  const nextOffset = parseDecimal(nextStop?.route_offset_meters ?? null)
  const distanceToNext =
    nextOffset !== null && startOffset !== null
      ? nextOffset - startOffset
      : null
  const distanceToDestination =
    startOffset !== null ? routeTotal - startOffset : null

  const totalPurchased = stops.reduce(
    (sum, stop) => sum + (parseDecimal(stop.fuel_added_gallons) ?? 0),
    0,
  )
  const totalCost = stops.reduce(
    (sum, stop) => sum + (parseDecimal(stop.fuel_cost) ?? 0),
    0,
  )
  const hasFuelCost = stops.some(
    (stop) => parseDecimal(stop.fuel_cost) !== null,
  )

  const startingFuel = start?.fuel_after_gallons ?? start?.fuel_before_gallons
  const remainingOnArrival =
    destination?.fuel_before_gallons ?? destination?.fuel_after_gallons

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Block title="Start">
        <Row label="Starting fuel" value={formatTripGallons(startingFuel)} />
        <Row
          label="Distance to next stop"
          value={distanceToNext === null ? "—" : formatMiles(distanceToNext)}
        />
        <Row
          label="Distance to destination"
          value={
            distanceToDestination === null
              ? "—"
              : formatMiles(distanceToDestination)
          }
        />
      </Block>
      <Block title="Destination">
        <Row
          label="Remaining fuel on arrival"
          value={formatTripGallons(remainingOnArrival)}
        />
        <Row
          label="Total fuel purchased"
          value={`${totalPurchased.toFixed(1)} gal`}
        />
        <Row
          label="Total fuel cost"
          value={hasFuelCost ? formatTripMoney(totalCost) : "—"}
        />
      </Block>
    </div>
  )
}
