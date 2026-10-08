/**
 * OptimizationWalkthrough component
 *
 * Step-by-step panel for reviewing a fuel optimization result: start,
 * every refuel stop (in order) and the destination. Supports Next/Back
 * navigation as well as jumping directly to any step. Stepping does not
 * change the map zoom level (handled by the caller via TomTomMapHandle.panTo).
 */

import { ChevronLeft, ChevronRight } from "lucide-react"
import type { OptimizationStep } from "@/lib/fuelOptimizationWalkthrough"

interface OptimizationWalkthroughProps {
  steps: OptimizationStep[]
  activeStepIndex: number
  onStepChange: (index: number) => void
}

function formatGallons(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  return `${value.toFixed(1)} gal`
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
  if (step.kind === "start") return "S"
  if (step.kind === "destination") return "D"
  return String(step.index)
}

export function OptimizationWalkthrough({
  steps,
  activeStepIndex,
  onStepChange,
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
              step.index === activeStepIndex
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
          <span className="text-xs text-muted-foreground flex-shrink-0 ml-2">
            Step {activeStepIndex + 1} of {steps.length}
          </span>
        </div>

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

        {activeStep.kind === "destination" && (
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
