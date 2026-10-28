/**
 * Driver trip list.
 *
 * A driver only ever sees the trips assigned to them, and reports progress
 * from here rather than editing anything about the route.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import { Loader2, Truck } from "lucide-react"

import { listMyTripPlans, updateTripPlanStatus } from "@/api/tripPlans"
import { type TripPlanStatus, UsersService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import {
  formatDateTime,
  formatDuration,
  formatMiles,
  TRIP_STATUS_CLASSES,
  TRIP_STATUS_LABELS,
} from "@/lib/tripPlans"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/my-trips")({
  component: MyTrips,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (user.role !== "driver") {
      throw redirect({ to: "/trips" })
    }
  },
  head: () => ({
    meta: [{ title: "My trips - Vector8" }],
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

function MyTripsList() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data, isLoading } = useQuery({
    queryKey: ["myTripPlans"],
    queryFn: () => listMyTripPlans(),
  })

  const mutation = useMutation({
    mutationFn: ({
      tripId,
      status,
    }: {
      tripId: string
      status: TripPlanStatus
    }) => updateTripPlanStatus(tripId, status),
    onSuccess: () => {
      showSuccessToast("Trip updated")
      queryClient.invalidateQueries({ queryKey: ["myTripPlans"] })
    },
    onError: (err) => handleError.call(showErrorToast, err),
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }

  const trips = data?.data ?? []

  if (trips.length === 0) {
    return (
      <div className="vector8-surface flex flex-col items-center justify-center py-12 text-center">
        <div className="mb-4 rounded-full bg-[color:rgba(217,142,43,0.08)] p-4">
          <Truck className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No trips assigned</h3>
        <p className="text-muted-foreground">
          Your dispatcher will send trips here once they are ready.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {trips.map((trip) => {
        const next = nextStatus(trip.status)
        const isPending =
          mutation.isPending && mutation.variables?.tripId === trip.id

        return (
          <div
            key={trip.id}
            className="vector8-surface flex flex-wrap items-center justify-between gap-4 p-4"
          >
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <Link
                  to="/my-trips/$tripId"
                  params={{ tripId: trip.id }}
                  className="font-semibold hover:underline"
                >
                  {trip.name}
                </Link>
                <Badge
                  variant="secondary"
                  className={TRIP_STATUS_CLASSES[trip.status]}
                >
                  {TRIP_STATUS_LABELS[trip.status]}
                </Badge>
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
              <p className="text-xs text-muted-foreground">
                Assigned {formatDateTime(trip.assigned_at)}
              </p>
            </div>
            {next ? (
              <Button
                disabled={isPending}
                onClick={() =>
                  mutation.mutate({ tripId: trip.id, status: next })
                }
              >
                {isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : null}
                {next === "in_progress" ? "Start trip" : "Mark completed"}
              </Button>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

function MyTrips() {
  return (
    <div className="flex w-full flex-col gap-6">
      <div>
        <p className="vector8-kicker">Driver</p>
        <h1 className="text-2xl font-semibold tracking-tight">My trips</h1>
        <p className="text-muted-foreground">
          Trips your dispatcher assigned to you, with the route already
          verified.
        </p>
      </div>
      <MyTripsList />
    </div>
  )
}
