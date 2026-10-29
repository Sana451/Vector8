/**
 * Dispatcher trip list.
 *
 * Trips are optimizer results that were frozen and refined through the routing
 * provider; from here a dispatcher reviews them and hands them to a driver.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router"
import { Route as RouteIcon, Trash2 } from "lucide-react"
import { useState } from "react"

import { deleteTripPlan, listTripPlans } from "@/api/tripPlans"
import { type TripPlanPublic, type UserPublic, UsersService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
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

function DeleteTripsDialog({
  trips,
  onClose,
  onDeleted,
}: {
  trips: TripPlanPublic[]
  onClose: () => void
  onDeleted: () => void
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: async (tripIds: string[]) => {
      const results = await Promise.allSettled(
        tripIds.map((id) => deleteTripPlan(id)),
      )
      const failed = results.filter((r) => r.status === "rejected").length
      return { total: tripIds.length, failed }
    },
    onSuccess: ({ total, failed }) => {
      if (failed === 0) {
        showSuccessToast(
          total === 1 ? "Trip deleted" : `Deleted ${total} trips`,
        )
      } else {
        showErrorToast(
          `Deleted ${total - failed} of ${total}, ${failed} failed`,
        )
      }
      onDeleted()
      onClose()
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tripPlans"] })
    },
  })

  const count = trips.length

  return (
    <Dialog open={count > 0} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {count === 1 ? "Delete trip?" : `Delete ${count} trips?`}
          </DialogTitle>
          <DialogDescription>
            {count === 1
              ? `The trip ${trips[0]?.vehicle_unit_number ?? ""} will be permanently deleted. This action cannot be undone.`
              : `${count} selected trips will be permanently deleted. This action cannot be undone.`}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2">
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            variant="destructive"
            loading={mutation.isPending}
            onClick={() => mutation.mutate(trips.map((t) => t.id))}
          >
            Delete
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function canDelete(trip: TripPlanPublic, user: UserPublic | null | undefined) {
  if (!user) return false
  if (user.is_superuser || user.role === "admin") return true
  return user.role === "dispatcher" && trip.owner_id === user.id
}

function TripsTable() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [pendingDelete, setPendingDelete] = useState<TripPlanPublic[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
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
  const deletableTrips = trips.filter((trip) => canDelete(trip, user))
  const selectedTrips = deletableTrips.filter((trip) =>
    selectedIds.has(trip.id),
  )
  const allSelected =
    deletableTrips.length > 0 && selectedTrips.length === deletableTrips.length

  const toggleOne = (tripId: string, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(tripId)
      else next.delete(tripId)
      return next
    })
  }

  const toggleAll = (checked: boolean) => {
    setSelectedIds(
      checked ? new Set(deletableTrips.map((t) => t.id)) : new Set(),
    )
  }

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
    <div className="space-y-3">
      {selectedTrips.length > 0 && (
        <div className="vector8-surface flex items-center justify-between gap-3 px-4 py-2">
          <span className="text-sm">Selected: {selectedTrips.length}</span>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setPendingDelete(selectedTrips)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete selected
          </Button>
        </div>
      )}
      <div className="vector8-surface overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox
                  aria-label="Select all trips"
                  disabled={deletableTrips.length === 0}
                  checked={allSelected}
                  onCheckedChange={(checked) => toggleAll(checked === true)}
                />
              </TableHead>
              <TableHead>Unit #</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>From</TableHead>
              <TableHead>To</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Distance</TableHead>
              <TableHead className="text-right">Duration</TableHead>
              <TableHead className="text-right">Stops</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {trips.map((trip) => (
              <TableRow
                key={trip.id}
                className="cursor-pointer"
                data-state={selectedIds.has(trip.id) ? "selected" : undefined}
                onClick={() =>
                  navigate({
                    to: "/trips/$tripId",
                    params: { tripId: trip.id },
                  })
                }
              >
                <TableCell onClick={(event) => event.stopPropagation()}>
                  {canDelete(trip, user) ? (
                    <Checkbox
                      aria-label={`Select trip ${trip.vehicle_unit_number ?? ""}`}
                      checked={selectedIds.has(trip.id)}
                      onCheckedChange={(checked) =>
                        toggleOne(trip.id, checked === true)
                      }
                    />
                  ) : null}
                </TableCell>
                <TableCell className="font-medium">
                  {trip.vehicle_unit_number ?? "—"}
                </TableCell>
                <TableCell>{trip.vehicle_name ?? "—"}</TableCell>
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
                <TableCell>
                  {canDelete(trip, user) ? (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Delete trip"
                      onClick={(event) => {
                        event.stopPropagation()
                        setPendingDelete([trip])
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  ) : null}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <DeleteTripsDialog
          trips={pendingDelete}
          onClose={() => setPendingDelete([])}
          onDeleted={() => setSelectedIds(new Set())}
        />
      </div>
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
