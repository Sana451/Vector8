/**
 * Shared presentation helpers for trip plans.
 */

import type { TripPlanStatus } from "@/client"

const METERS_PER_MILE = 1609.344
const SECONDS_PER_HOUR = 3600
const SECONDS_PER_MINUTE = 60

export const TRIP_STATUS_LABELS: Record<TripPlanStatus, string> = {
  draft: "Draft",
  refined: "Refined",
  refine_failed: "Refine failed",
  assigned: "Assigned",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
}

/** Tailwind classes per status, so a dispatcher can scan a list by colour. */
export const TRIP_STATUS_CLASSES: Record<TripPlanStatus, string> = {
  draft: "bg-muted text-muted-foreground",
  refined: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  refine_failed: "bg-destructive/15 text-destructive",
  assigned: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  in_progress: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  completed: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  cancelled: "bg-muted text-muted-foreground line-through",
}

export function formatMiles(meters: number | null | undefined): string {
  if (meters === null || meters === undefined) {
    return "—"
  }
  return `${(meters / METERS_PER_MILE).toFixed(1)} mi`
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) {
    return "—"
  }
  const hours = Math.floor(seconds / SECONDS_PER_HOUR)
  const minutes = Math.round((seconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE)
  return hours > 0 ? `${hours} h ${minutes} min` : `${minutes} min`
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "—"
  }
  return new Date(value).toLocaleString()
}

/** Render a signed delta, so "+12.4 mi" reads as extra driving. */
export function formatDelta(
  value: number,
  format: (value: number) => string,
): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "±"
  return `${sign}${format(Math.abs(value))}`
}
