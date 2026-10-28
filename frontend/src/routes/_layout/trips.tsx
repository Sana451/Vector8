/**
 * Dispatcher trip list.
 *
 * Trips are optimizer results that were frozen and refined through the routing
 * provider; from here a dispatcher reviews them and hands them to a driver.
 */

import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import { Route as RouteIcon } from "lucide-react"

import { listTripPlans } from "@/api/tripPlans"
import { UsersService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  formatDateTime,
  formatDuration,
  formatMiles,
  TRIP_STATUS_CLASSES,
  TRIP_STATUS_LABELS,
} from "@/lib/tripPlans"

export const Route = createFileRoute("/_layout/trips")({
  component: Trips,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (user.role === "driver") {
      throw redirect({ to: "/my-trips" })
    }
  },
  head: () => ({
    meta: [{ title: "Trips - Vector8" }],
  }),
})

function TripsTable() {
  const { data, isLoading } = useQuery({
    queryKey: ["tripPlans"],
    queryFn: () => listTripPlans(),
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  const trips = data?.data ?? []

  if (trips.length === 0) {
    return (
      <div className="vector8-surface flex flex-col items-center justify-center py-12 text-center">
        <div className="mb-4 rounded-full bg-[color:rgba(217,142,43,0.08)] p-4">
          <RouteIcon className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No trips saved yet</h3>
        <p className="text-muted-foreground">
          Run the fuel optimizer on the map, then refine the route to save it as
          a trip.
        </p>
      </div>
    )
  }

  return (
    <div className="vector8-surface overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Trip</TableHead>
            <TableHead>From</TableHead>
            <TableHead>To</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Distance</TableHead>
            <TableHead className="text-right">Duration</TableHead>
            <TableHead className="text-right">Stops</TableHead>
            <TableHead>Created</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {trips.map((trip) => (
            <TableRow key={trip.id}>
              <TableCell>
                <Link
                  to="/trips/$tripId"
                  params={{ tripId: trip.id }}
                  className="font-medium underline-offset-4 hover:underline"
                >
                  {trip.name}
                </Link>
              </TableCell>
              <TableCell
                className="max-w-[220px] truncate"
                title={trip.origin_label ?? undefined}
              >
                {trip.origin_label ?? "—"}
              </TableCell>
              <TableCell
                className="max-w-[220px] truncate"
                title={trip.destination_label ?? undefined}
              >
                {trip.destination_label ?? "—"}
              </TableCell>
              <TableCell>
                <Badge
                  variant="secondary"
                  className={TRIP_STATUS_CLASSES[trip.status]}
                >
                  {TRIP_STATUS_LABELS[trip.status]}
                </Badge>
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatMiles(
                  trip.refined_distance_meters ?? trip.base_distance_meters,
                )}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatDuration(
                  trip.refined_duration_seconds ?? trip.base_duration_seconds,
                )}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {trip.number_of_stops}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDateTime(trip.created_at)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function Trips() {
  return (
    <div className="flex w-full flex-col gap-6">
      <div>
        <p className="vector8-kicker">Dispatch</p>
        <h1 className="text-2xl font-semibold tracking-tight">Trips</h1>
        <p className="text-muted-foreground">
          Saved optimizer runs with provider-verified routes, ready to assign.
        </p>
      </div>
      <TripsTable />
    </div>
  )
}
