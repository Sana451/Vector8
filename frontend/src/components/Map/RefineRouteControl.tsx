/**
 * RefineRouteControl component
 *
 * The optimizer estimates every fuel stop as a detour off the base route. This
 * control asks the backend to build a trip plan, which sends the selected stops
 * back to the routing provider as waypoints and returns the route that actually
 * drives into each of them. The refined geometry is handed to the parent so it
 * can be drawn as its own map layer and compared against the base route.
 */

import { useMutation } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { ExternalLink, Loader2, Route as RouteIcon } from "lucide-react"
import { createTripPlan, refineTripPlan } from "@/api/tripPlans"
import type { TripPlanDetailPublic } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const METERS_PER_MILE = 1609.344
const SECONDS_PER_MINUTE = 60

interface RefineRouteControlProps {
  /** Optimization run to turn into a trip plan. */
  optimizationRunId?: string | null
  tripPlan: TripPlanDetailPublic | null
  onTripPlanChange: (tripPlan: TripPlanDetailPublic) => void
}

function formatMiles(meters: number): string {
  return `${(meters / METERS_PER_MILE).toFixed(1)} mi`
}

function formatMinutes(seconds: number): string {
  return `${Math.round(seconds / SECONDS_PER_MINUTE)} min`
}

function formatDelta(value: number, format: (value: number) => string): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "±"
  return `${sign}${format(Math.abs(value))}`
}

export function RefineRouteControl({
  optimizationRunId,
  tripPlan,
  onTripPlanChange,
}: RefineRouteControlProps) {
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: async (): Promise<TripPlanDetailPublic> => {
      if (tripPlan) {
        return refineTripPlan(tripPlan.id, { force_refresh: true })
      }
      if (!optimizationRunId) {
        throw new Error("No optimization run to refine")
      }
      return createTripPlan({ optimization_run_id: optimizationRunId })
    },
    onSuccess: (data) => {
      onTripPlanChange(data)
      if (data.refine_error) {
        showErrorToast(data.refine_error)
        return
      }
      showSuccessToast("Refined route is ready")
    },
    onError: (error) => {
      handleError.call(showErrorToast, error as Error)
    },
  })

  if (!optimizationRunId) {
    return null
  }

  const delta = tripPlan?.delta ?? null
  const refinedDistance = tripPlan?.refined_distance_meters ?? null
  const refinedDuration = tripPlan?.refined_duration_seconds ?? null

  return (
    <div className="border-t border-border/50 px-3 py-2">
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="flex w-full items-center justify-center gap-1.5 rounded-md bg-primary/10 px-2 py-1.5 text-xs font-medium text-primary hover:bg-primary/20 disabled:opacity-50"
      >
        {mutation.isPending ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <RouteIcon className="h-3.5 w-3.5" />
        )}
        {tripPlan ? "Recalculate refined route" : "Refine route via stops"}
      </button>

      {tripPlan && (
        <Link
          to="/trips/$tripId"
          params={{ tripId: tripPlan.id }}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-md border border-border px-2 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          Open saved route
        </Link>
      )}

      {tripPlan?.refine_error && (
        <p className="mt-2 rounded-md border border-destructive/30 bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
          {tripPlan.refine_error}
        </p>
      )}

      {tripPlan && refinedDistance !== null && refinedDuration !== null && (
        <dl className="mt-2 grid grid-cols-3 gap-x-2 gap-y-1 text-xs">
          <dt className="col-span-1 text-muted-foreground">&nbsp;</dt>
          <dd className="col-span-1 font-medium text-foreground">Distance</dd>
          <dd className="col-span-1 font-medium text-foreground">Time</dd>

          <dt className="col-span-1 text-muted-foreground">Planned</dt>
          <dd className="col-span-1 tabular-nums">
            {formatMiles(tripPlan.base_distance_meters)}
          </dd>
          <dd className="col-span-1 tabular-nums">
            {formatMinutes(tripPlan.base_duration_seconds)}
          </dd>

          <dt className="col-span-1 text-muted-foreground">Refined</dt>
          <dd className="col-span-1 tabular-nums">
            {formatMiles(refinedDistance)}
          </dd>
          <dd className="col-span-1 tabular-nums">
            {formatMinutes(refinedDuration)}
          </dd>

          {delta && (
            <>
              <dt className="col-span-1 text-muted-foreground">Detour</dt>
              <dd className="col-span-1 tabular-nums text-amber-600 dark:text-amber-400">
                {formatDelta(delta.distance_meters, formatMiles)}
              </dd>
              <dd className="col-span-1 tabular-nums text-amber-600 dark:text-amber-400">
                {formatDelta(delta.duration_seconds, formatMinutes)}
              </dd>
            </>
          )}
        </dl>
      )}
    </div>
  )
}
