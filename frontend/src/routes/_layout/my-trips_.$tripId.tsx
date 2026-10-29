/**
 * Driver trip detail.
 *
 * The driver's working view of one assigned trip: the verified route on a map,
 * the stops in travel order, downloads for the truck GPS and the single status
 * change they are allowed to make.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import { ArrowLeft, Loader2 } from "lucide-react"
import { useState } from "react"

import { readTripPlan, updateTripPlanStatus } from "@/api/tripPlans"
import { type TripPlanStatus, UsersService } from "@/client"
import { TripActions } from "@/components/TripPlans/TripActions"
import { TripRouteMap } from "@/components/TripPlans/TripRouteMap"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useCustomToast from "@/hooks/useCustomToast"
import {
  formatDuration,
  formatMiles,
  TRIP_STATUS_CLASSES,
  TRIP_STATUS_LABELS,
} from "@/lib/tripPlans"
import {
  formatTripDetour,
  formatTripGallons,
  formatTripMoney,
  isTankFullAfterRefuel,
  parseDecimal,
} from "@/lib/tripStopFormat"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/my-trips_/$tripId")({
  component: DriverTripDetail,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (user.role !== "driver") {
      throw redirect({ to: "/trips" })
    }
  },
  head: () => ({
    meta: [{ title: "Trip - Vector8" }],
  }),
})

/** The only transition a driver can make from the current status, if any. */
function nextStatus(status: TripPlanStatus): TripPlanStatus | null {
  if (status === "assigned") {
    return "in_progress"
  }
  if (status === "in_progress") {
    return "completed"
  }
  return null
}

function DriverTripDetail() {
  const { tripId } = Route.useParams()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [focusStop, setFocusStop] = useState<{
    coordinate: [number, number]
    key: number
  } | null>(null)

  const { data: trip, isLoading } = useQuery({
    queryKey: ["tripPlan", tripId],
    queryFn: () => readTripPlan(tripId),
  })

  const mutation = useMutation({
    mutationFn: (status: TripPlanStatus) =>
      updateTripPlanStatus(tripId, status),
    onSuccess: () => {
      showSuccessToast("Trip updated")
      queryClient.invalidateQueries({ queryKey: ["tripPlan", tripId] })
      queryClient.invalidateQueries({ queryKey: ["myTripPlans"] })
    },
    onError: (err) => handleError.call(showErrorToast, err),
  })

  if (isLoading || !trip) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-80 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const next = nextStatus(trip.status)

  return (
    <div className="flex w-full flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link
          to="/my-trips"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to my trips
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">
              {trip.name}
            </h1>
            {trip.vehicle_name || trip.vehicle_unit_number ? (
              <span className="text-sm text-muted-foreground">
                {[trip.vehicle_unit_number, trip.vehicle_name]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            ) : null}
            <Badge
              variant="secondary"
              className={TRIP_STATUS_CLASSES[trip.status]}
            >
              {TRIP_STATUS_LABELS[trip.status]}
            </Badge>
          </div>
          {next ? (
            <Button
              disabled={mutation.isPending}
              onClick={() => mutation.mutate(next)}
            >
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              {next === "in_progress" ? "Start trip" : "Mark completed"}
            </Button>
          ) : null}
        </div>
        <p className="text-sm text-muted-foreground tabular-nums">
          {formatMiles(
            trip.refined_distance_meters ?? trip.base_distance_meters,
          )}
          {" · "}
          {formatDuration(
            trip.refined_duration_seconds ?? trip.base_duration_seconds,
          )}
          {" · "}
          {trip.number_of_stops} stops
        </p>
        {trip.refine_error ? (
          <p className="text-sm text-destructive">
            This route could not be verified by the provider:{" "}
            {trip.refine_error}
          </p>
        ) : null}
      </div>

      <TripRouteMap
        trip={trip}
        focusStop={focusStop}
        className="relative h-[600px] w-full overflow-hidden rounded-lg border bg-background"
      />

      <TripActions trip={trip} />

      <div className="vector8-surface overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">#</TableHead>
              <TableHead>Stop</TableHead>
              <TableHead className="text-right">Fuel on arrival</TableHead>
              <TableHead className="text-right">Fuel to add</TableHead>
              <TableHead className="text-right">Fuel after refuel</TableHead>
              <TableHead className="text-right">Price per gallon</TableHead>
              <TableHead className="text-right">Detour</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(trip.stops ?? []).map((stop) => {
              const fuelAdded = parseDecimal(stop.fuel_added_gallons)
              const isFull = isTankFullAfterRefuel(
                stop.fuel_after_gallons,
                trip.usable_tank_gallons,
              )
              return (
                <TableRow
                  key={`${stop.sequence}-${stop.label}`}
                  className="cursor-pointer"
                  onClick={() =>
                    setFocusStop({
                      coordinate: stop.coordinate as [number, number],
                      key: Date.now(),
                    })
                  }
                >
                  <TableCell className="tabular-nums">
                    {stop.sequence}
                  </TableCell>
                  <TableCell>
                    <span className="font-medium">{stop.label}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      {stop.kind}
                    </span>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatTripGallons(stop.fuel_before_gallons)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {fuelAdded === null ? (
                      "—"
                    ) : (
                      <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                        +{fuelAdded.toFixed(1)} gal
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatTripGallons(stop.fuel_after_gallons)}
                    {isFull ? (
                      <span className="ml-1 text-muted-foreground">(full)</span>
                    ) : null}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatTripMoney(stop.fuel_price_per_gallon)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatTripDetour(
                      stop.detour_distance_meters,
                      stop.detour_time_seconds,
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
