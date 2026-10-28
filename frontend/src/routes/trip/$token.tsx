/**
 * Public trip page behind a share link.
 *
 * Lives outside `_layout` so visitors without an account are never sent to
 * the login screen. The token in the URL is the only credential.
 */

import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { readSharedTripPlan } from "@/api/tripPlans"
import { TripRouteMap } from "@/components/TripPlans/TripRouteMap"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  formatDateTime,
  formatDuration,
  formatMiles,
  TRIP_STATUS_CLASSES,
  TRIP_STATUS_LABELS,
} from "@/lib/tripPlans"

export const Route = createFileRoute("/trip/$token")({
  component: SharedTrip,
  head: () => ({
    meta: [{ title: "Shared trip - Vector8" }],
  }),
})

function SharedTrip() {
  const { token } = Route.useParams()
  const {
    data: trip,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["sharedTripPlan", token],
    queryFn: () => readSharedTripPlan(token),
    retry: false,
  })

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-3 p-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  if (isError || !trip) {
    return (
      <div className="mx-auto max-w-4xl p-8 text-center">
        <h1 className="text-xl font-semibold">Trip not available</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          This link is invalid or has been revoked.
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{trip.name}</h1>
        <Badge variant="secondary" className={TRIP_STATUS_CLASSES[trip.status]}>
          {TRIP_STATUS_LABELS[trip.status]}
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        {formatMiles(trip.distance_meters)} ·{" "}
        {formatDuration(trip.duration_seconds)} · {trip.number_of_stops} stops ·
        created {formatDateTime(trip.created_at)}
      </p>

      <TripRouteMap
        trip={{
          stops: trip.stops ?? [],
          refined_geometry: trip.geometry ?? null,
          base_geometry: null,
        }}
        className="relative h-[420px] w-full overflow-hidden rounded-lg border"
      />

      <ol className="vector8-surface divide-y">
        {(trip.stops ?? []).map((stop) => (
          <li
            key={`${stop.sequence}-${stop.label}`}
            className="flex items-center gap-3 p-3 text-sm"
          >
            <span className="w-6 tabular-nums text-muted-foreground">
              {stop.sequence}
            </span>
            <span className="flex-1 font-medium">{stop.label}</span>
            <span className="tabular-nums text-muted-foreground">
              {stop.fuel_added_gallons
                ? `${Number(stop.fuel_added_gallons).toFixed(1)} gal`
                : ""}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}
