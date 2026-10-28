/**
 * Dispatcher trip detail.
 *
 * Shows the frozen optimizer stops next to the provider-verified route and
 * lets the dispatcher hand the trip to a driver. The trailing underscore in the
 * file name keeps this page out of the trip list's layout.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import { ArrowLeft, Link2, Loader2 } from "lucide-react"
import { useState } from "react"

import { listDrivers } from "@/api/drivers"
import { assignTripPlan, readTripPlan, shareTripPlan } from "@/api/tripPlans"
import { UsersService } from "@/client"
import { TripActions } from "@/components/TripPlans/TripActions"
import { TripRouteMap } from "@/components/TripPlans/TripRouteMap"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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
  formatDateTime,
  formatDelta,
  formatDuration,
  formatMiles,
  TRIP_STATUS_CLASSES,
  TRIP_STATUS_LABELS,
} from "@/lib/tripPlans"
import { handleError } from "@/utils"

const UNASSIGNED = "unassigned"

export const Route = createFileRoute("/_layout/trips_/$tripId")({
  component: TripDetail,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (user.role === "driver") {
      throw redirect({ to: "/my-trips" })
    }
  },
  head: () => ({
    meta: [{ title: "Trip - Vector8" }],
  }),
})

function AssignmentCard({
  tripId,
  assignedDriverId,
  assignedAt,
}: {
  tripId: string
  assignedDriverId: string | null
  assignedAt: string | null
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [selected, setSelected] = useState(assignedDriverId ?? UNASSIGNED)

  const { data: drivers } = useQuery({
    queryKey: ["drivers"],
    queryFn: () => listDrivers(),
  })

  const mutation = useMutation({
    mutationFn: (driverId: string | null) => assignTripPlan(tripId, driverId),
    onSuccess: (trip) => {
      showSuccessToast(
        trip.assigned_driver_id ? "Trip assigned" : "Trip unassigned",
      )
      queryClient.invalidateQueries({ queryKey: ["tripPlan", tripId] })
      queryClient.invalidateQueries({ queryKey: ["tripPlans"] })
    },
    onError: (err) => handleError.call(showErrorToast, err),
  })

  const hasChanges = selected !== (assignedDriverId ?? UNASSIGNED)

  return (
    <div className="vector8-surface flex flex-col gap-3 p-4">
      <div>
        <p className="vector8-kicker">Assignment</p>
        <p className="text-sm text-muted-foreground">
          {assignedDriverId
            ? `Assigned ${formatDateTime(assignedAt)}`
            : "Not assigned to a driver yet"}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Select value={selected} onValueChange={setSelected}>
          <SelectTrigger className="w-72">
            <SelectValue placeholder="Select a driver" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={UNASSIGNED}>No driver</SelectItem>
            {(drivers?.data ?? []).map((driver) => (
              <SelectItem key={driver.id} value={driver.id}>
                {driver.full_name ?? driver.email}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          disabled={!hasChanges || mutation.isPending}
          onClick={() =>
            mutation.mutate(selected === UNASSIGNED ? null : selected)
          }
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : null}
          Save
        </Button>
      </div>
    </div>
  )
}

function ShareCard({
  tripId,
  isShared,
}: {
  tripId: string
  isShared: boolean
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (enabled: boolean) => shareTripPlan(tripId, enabled),
    onSuccess: async (token) => {
      if (token) {
        await navigator.clipboard
          ?.writeText(`${window.location.origin}/trip/${token}`)
          .catch(() => undefined)
        showSuccessToast("Link copied to clipboard")
      } else {
        showSuccessToast("Link revoked")
      }
      queryClient.invalidateQueries({ queryKey: ["tripPlan", tripId] })
    },
    onError: (err) => handleError.call(showErrorToast, err),
  })

  return (
    <div className="vector8-surface flex flex-col gap-3 p-4">
      <div>
        <p className="vector8-kicker">Public link</p>
        <p className="text-sm text-muted-foreground">
          {isShared
            ? "Anyone with the link can view this trip without an account."
            : "Share a read-only view of this trip."}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate(true)}
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Link2 className="h-4 w-4" />
          )}
          {isShared ? "Copy link" : "Create link"}
        </Button>
        {isShared ? (
          <Button
            variant="outline"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate(false)}
          >
            Revoke
          </Button>
        ) : null}
      </div>
    </div>
  )
}

function SummaryCard({
  label,
  value,
  hint,
}: {
  label: string
  value: string
  hint?: string
}) {
  return (
    <div className="vector8-surface p-4">
      <p className="vector8-kicker">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

function TripDetail() {
  const { tripId } = Route.useParams()
  const [focusStop, setFocusStop] = useState<{
    coordinate: [number, number]
    key: number
  } | null>(null)
  const { data: trip, isLoading } = useQuery({
    queryKey: ["tripPlan", tripId],
    queryFn: () => readTripPlan(tripId),
  })

  if (isLoading || !trip) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  return (
    <div className="flex w-full flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link
          to="/trips"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to trips
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{trip.name}</h1>
          <Badge
            variant="secondary"
            className={TRIP_STATUS_CLASSES[trip.status]}
          >
            {TRIP_STATUS_LABELS[trip.status]}
          </Badge>
        </div>
        {trip.refine_error ? (
          <p className="text-sm text-destructive">
            Route refinement failed: {trip.refine_error}
          </p>
        ) : null}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label="Distance"
          value={formatMiles(
            trip.refined_distance_meters ?? trip.base_distance_meters,
          )}
          hint={
            trip.delta
              ? `${formatDelta(trip.delta.distance_meters, formatMiles)} vs planned`
              : undefined
          }
        />
        <SummaryCard
          label="Duration"
          value={formatDuration(
            trip.refined_duration_seconds ?? trip.base_duration_seconds,
          )}
          hint={
            trip.delta
              ? `${formatDelta(trip.delta.duration_seconds, formatDuration)} vs planned`
              : undefined
          }
        />
        <SummaryCard label="Stops" value={String(trip.number_of_stops)} />
        <SummaryCard
          label="Provider"
          value={trip.refined_provider ?? "—"}
          hint={`Created ${formatDateTime(trip.created_at)}`}
        />
      </div>

      <AssignmentCard
        tripId={trip.id}
        assignedDriverId={trip.assigned_driver_id ?? null}
        assignedAt={trip.assigned_at ?? null}
      />

      <ShareCard tripId={trip.id} isShared={trip.is_shared ?? false} />

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
              <TableHead className="text-right">Fuel added</TableHead>
              <TableHead className="text-right">Price / gal</TableHead>
              <TableHead className="text-right">Cost</TableHead>
              <TableHead className="text-right">Detour</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(trip.stops ?? []).map((stop) => (
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
                <TableCell className="tabular-nums">{stop.sequence}</TableCell>
                <TableCell>
                  <span className="font-medium">{stop.label}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {stop.kind}
                  </span>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {stop.fuel_added_gallons
                    ? `${Number(stop.fuel_added_gallons).toFixed(1)} gal`
                    : "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {stop.fuel_price_per_gallon
                    ? `$${Number(stop.fuel_price_per_gallon).toFixed(2)}`
                    : "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {stop.fuel_cost
                    ? `$${Number(stop.fuel_cost).toFixed(2)}`
                    : "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {stop.detour_distance_meters
                    ? formatMiles(Number(stop.detour_distance_meters))
                    : "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
