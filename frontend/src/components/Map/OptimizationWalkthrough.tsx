/**
 * OptimizationWalkthrough component
 *
 * Step-by-step panel for reviewing reached route points and unreachable
 * optimization targets. Supports Next/Back navigation and direct jumps.
 * Stepping does not change the map zoom level.
 */

import { ChevronLeft, ChevronRight } from "lucide-react"
import type { FuelOptimizationFailurePublic } from "@/client"
import type { OptimizationStep } from "@/lib/fuelOptimizationWalkthrough"

interface OptimizationWalkthroughProps {
  steps: OptimizationStep[]
  activeStepIndex: number
  onStepChange: (index: number) => void
  failure: FuelOptimizationFailurePublic | null
}

function formatGallons(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  return `${value.toFixed(1)} gal`
}

function formatDiagnosticGallons(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  return `${value.toFixed(4)} gal`
}

function formatMoney(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  return `$${value.toFixed(2)}`
}

function formatMeters(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  return `${(value / 1000).toFixed(1)} km`
}

function formatSeconds(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  return `${Math.round(value / 60)} min`
}

function stepBadgeLabel(step: OptimizationStep): string {
  if (step.isPrimaryFailureTarget) return "X"
  if (step.kind === "unreachable_station") return "X"
  if (step.kind === "checkpoint") return "✓"
  if (step.kind === "start") return "S"
  if (step.kind === "destination") return "D"
  return String(step.index)
}

export function OptimizationWalkthrough({
  steps,
  activeStepIndex,
  onStepChange,
  failure,
}: OptimizationWalkthroughProps) {
  if (steps.length === 0) {
    return null
  }

  const activeStep = steps[activeStepIndex] ?? steps[0]
  const canGoBack = activeStepIndex > 0
  const canGoNext = activeStepIndex < steps.length - 1

  return (
    <div className="absolute bottom-4 left-4 z-10 w-[360px] max-w-[calc(100vw-2rem)] rounded-lg border border-border/70 bg-white dark:bg-slate-950 shadow-md">
      {/* Step jump pills */}
      <div className="flex items-center gap-1.5 px-3 pt-3 overflow-x-auto">
        {steps.map((step) => (
          <button
            key={step.index}
            type="button"
            onClick={() => onStepChange(step.index)}
            aria-current={step.index === activeStepIndex}
            aria-label={`Go to ${step.label}`}
            className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
              step.isPrimaryFailureTarget
                ? "bg-red-600 text-white"
                : step.status === "unreachable"
                  ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300"
                  : step.index === activeStepIndex
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {stepBadgeLabel(step)}
          </button>
        ))}
      </div>

      {/* Step details */}
      <div className="px-4 py-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold truncate">{activeStep.label}</h3>
          <span
            className={`text-xs flex-shrink-0 ml-2 ${
              activeStep.status === "unreachable"
                ? "font-semibold text-red-600 dark:text-red-400"
                : "text-muted-foreground"
            }`}
          >
            {activeStep.status === "unreachable" ? "Unreachable" : "Reached"} ·{" "}
            {activeStepIndex + 1}/{steps.length}
          </span>
        </div>

        {failure && (
          <div className="mt-2 rounded-md border border-red-200 bg-red-50 px-2.5 py-2 text-xs text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200">
            <div className="font-semibold">{failure.message}</div>
            <div className="mt-1">
              Stopped at{" "}
              {formatMeters(Number(failure.stopped_at_route_offset_meters))}
              {failure.last_reachable_station_id
                ? ` after station ${failure.last_reachable_station_id}`
                : " from the route start"}
              .
            </div>
          </div>
        )}

        {activeStep.kind === "start" && (
          <div className="mt-2 text-xs space-y-1">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Starting fuel</span>
              <span className="font-medium">
                {formatGallons(activeStep.fuelGallons)}
              </span>
            </div>
          </div>
        )}

        {activeStep.kind === "checkpoint" && (
          <div className="mt-2 text-xs space-y-1">
            <div className="text-muted-foreground">
              Reached without refueling
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Fuel on arrival</span>
              <span className="font-medium">
                {formatGallons(activeStep.fuelGallons)}
              </span>
            </div>
          </div>
        )}

        {activeStep.kind === "stop" && (
          <div className="mt-2 text-xs space-y-1">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Fuel on arrival</span>
              <span className="font-medium">
                {formatGallons(activeStep.fuelBeforeGallons)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Fuel to add</span>
              <span className="font-medium text-emerald-600 dark:text-emerald-400">
                +{formatGallons(activeStep.fuelAddedGallons)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Fuel after refuel</span>
              <span className="font-medium">
                {formatGallons(activeStep.fuelAfterGallons)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Price per gallon</span>
              <span className="font-medium">
                {formatMoney(activeStep.fuelPricePerGallon)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Cost at this stop</span>
              <span className="font-medium">
                {formatMoney(activeStep.fuelCost)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Detour</span>
              <span className="font-medium">
                {formatMeters(activeStep.detourDistanceMeters)} /{" "}
                {formatSeconds(activeStep.detourTimeSeconds)}
              </span>
            </div>
          </div>
        )}

        {activeStep.status === "unreachable" && (
          <div className="mt-2 text-xs space-y-1">
            <div className="font-semibold text-red-600 dark:text-red-400">
              {activeStep.isPrimaryFailureTarget
                ? "Primary failure target"
                : "Unreachable goal"}
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Fuel required</span>
              <span className="font-medium">
                {formatDiagnosticGallons(activeStep.fuelRequiredGallons)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Fuel available</span>
              <span className="font-medium">
                {formatDiagnosticGallons(activeStep.availableFuelGallons)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Required reserve</span>
              <span className="font-medium">
                {formatDiagnosticGallons(activeStep.reserveGallons)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Reserve deficit</span>
              <span className="font-semibold text-red-600 dark:text-red-400">
                {formatDiagnosticGallons(activeStep.deficitGallons)}
              </span>
            </div>
          </div>
        )}

        {activeStep.kind === "destination" &&
          activeStep.status === "reached" && (
            <div className="mt-2 text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-muted-foreground">
                  Remaining fuel on arrival
                </span>
                <span className="font-medium">
                  {formatGallons(activeStep.fuelGallons)}
                </span>
              </div>
            </div>
          )}
        {activeStep.isFailurePoint && activeStep.status === "reached" && (
          <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            Last reachable point; the algorithm could not continue beyond here.
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between border-t border-border/50 px-3 py-2">
        <button
          type="button"
          onClick={() => onStepChange(activeStepIndex - 1)}
          disabled={!canGoBack}
          className="flex items-center gap-1 text-xs font-medium px-2 py-1.5 rounded-md hover:bg-muted disabled:opacity-40 disabled:hover:bg-transparent"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Back
        </button>
        <button
          type="button"
          onClick={() => onStepChange(activeStepIndex + 1)}
          disabled={!canGoNext}
          className="flex items-center gap-1 text-xs font-medium px-2 py-1.5 rounded-md hover:bg-muted disabled:opacity-40 disabled:hover:bg-transparent"
        >
          Next
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
