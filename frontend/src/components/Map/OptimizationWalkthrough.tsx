/**
 * OptimizationWalkthrough component
 *
 * Step-by-step panel for reviewing reached route points and unreachable
 * optimization targets. Supports Next/Back navigation and direct jumps.
 * The details can be collapsed; pills and navigation stay visible.
 * Stepping does not change the map zoom level.
 */

import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from "lucide-react"
import { useRef, useState } from "react"
import type {
  FuelOptimizationEconomicsPublic,
  FuelOptimizationFailurePublic,
  FuelOptimizationSummaryPublic,
} from "@/client"
import { StopSelectionDetails } from "@/components/Map/StopSelectionDetails"
import { useDraggable } from "@/hooks/useDraggable"
import type { OptimizationStep } from "@/lib/fuelOptimizationWalkthrough"

interface OptimizationWalkthroughProps {
  steps: OptimizationStep[]
  activeStepIndex: number
  onStepChange: (index: number) => void
  failure: FuelOptimizationFailurePublic | null
  economics?: FuelOptimizationEconomicsPublic | null
  onComparisonOpenChange?: (open: boolean) => void
  consumptionMpg?: number | string
  usableTankGallons?: number | string
  summary?: FuelOptimizationSummaryPublic
  routeTotalDistanceMeters?: number
  reserveGallons?: number
}

function formatGallons(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  return `${value.toFixed(1)} gal`
}

function formatMiles(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  return `${value.toFixed(1)} mi`
}

function formatDiagnosticGallons(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  return `${value.toFixed(2)} gal`
}

function formatMoney(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  return `$${value.toFixed(2)}`
}

function formatMeters(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  return `${(value / 1000).toFixed(1)} km`
}

function formatMetersAsMiles(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  return formatMiles(value / 1609.344)
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
  economics,
  onComparisonOpenChange,
  consumptionMpg,
  usableTankGallons,
  summary,
  routeTotalDistanceMeters,
  reserveGallons,
}: OptimizationWalkthroughProps) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const { dragHandlers, dragStyle } = useDraggable(panelRef)

  if (steps.length === 0) {
    return null
  }

  const activeStep = steps[activeStepIndex] ?? steps[0]
  const nextStep = steps[activeStepIndex + 1]
  const distanceToNextMeters =
    nextStep && activeStep
      ? nextStep.routeOffsetMeters - activeStep.routeOffsetMeters
      : undefined
  const destinationOffsetMeters =
    routeTotalDistanceMeters ?? steps[steps.length - 1]?.routeOffsetMeters
  const distanceToDestinationMeters =
    destinationOffsetMeters !== undefined && activeStep.kind !== "destination"
      ? destinationOffsetMeters - activeStep.routeOffsetMeters
      : undefined
  const mpg = Number(consumptionMpg)
  const usableTank = Number(usableTankGallons)
  const isFullAfterRefuel =
    activeStep.kind === "stop" &&
    activeStep.fuelAfterGallons !== undefined &&
    usableTank > 0 &&
    Math.abs(activeStep.fuelAfterGallons - usableTank) < 0.05
  const fuelOnDepartureGallons =
    activeStep.kind === "start"
      ? activeStep.fuelGallons
      : activeStep.fuelAfterGallons
  const rangeMiles =
    fuelOnDepartureGallons !== undefined && mpg > 0
      ? fuelOnDepartureGallons * mpg
      : undefined
  const rangeWithoutReserveMiles =
    fuelOnDepartureGallons !== undefined && mpg > 0
      ? Math.max(0, fuelOnDepartureGallons - (reserveGallons ?? 0)) * mpg
      : undefined
  const canGoBack = activeStepIndex > 0
  const canGoNext = activeStepIndex < steps.length - 1

  return (
    <div
      ref={panelRef}
      {...dragHandlers}
      style={dragStyle}
      className="absolute bottom-4 left-4 z-10 w-[360px] max-w-[calc(100vw-2rem)] rounded-lg border border-border/70 bg-white dark:bg-slate-950 shadow-md"
    >
      {/* Step jump pills */}
      <div className="flex items-center gap-1.5 px-3 pt-3">
        <div className="flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto">
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
        <button
          type="button"
          onClick={() => setIsCollapsed((value) => !value)}
          aria-expanded={!isCollapsed}
          aria-label={isCollapsed ? "Expand details" : "Collapse details"}
          className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
        >
          {isCollapsed ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Step details */}
      {!isCollapsed && (
        <div className="px-4 py-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold truncate">
              {activeStep.label}
            </h3>
            <span
              className={`text-xs flex-shrink-0 ml-2 ${
                activeStep.status === "unreachable"
                  ? "font-semibold text-red-600 dark:text-red-400"
                  : "text-muted-foreground"
              }`}
            >
              {activeStep.status === "unreachable" ? "Unreachable" : "Reached"}{" "}
              · {activeStepIndex + 1}/{steps.length}
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
              {distanceToNextMeters !== undefined && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">
                    Distance to next stop
                  </span>
                  <span className="font-medium">
                    {formatMetersAsMiles(distanceToNextMeters)}
                  </span>
                </div>
              )}
              {rangeMiles !== undefined && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Range on fuel</span>
                  <span className="font-medium">{formatMiles(rangeMiles)}</span>
                </div>
              )}
              {rangeWithoutReserveMiles !== undefined && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">
                    Range without reserve
                  </span>
                  <span className="font-medium">
                    {formatMiles(rangeWithoutReserveMiles)}
                  </span>
                </div>
              )}
              {distanceToDestinationMeters !== undefined && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">
                    Distance to destination
                  </span>
                  <span className="font-medium">
                    {formatMetersAsMiles(distanceToDestinationMeters)}
                  </span>
                </div>
              )}
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
              <div className="flex justify-between">
                <span className="text-muted-foreground">
                  Distance to destination
                </span>
                <span className="font-medium">
                  {formatMetersAsMiles(distanceToDestinationMeters)}
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
                  {isFullAfterRefuel && (
                    <span className="text-muted-foreground"> (full)</span>
                  )}
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
              <StopSelectionDetails
                selection={activeStep.selection}
                lookahead={activeStep.lookahead}
                economics={economics}
                onOpenChange={onComparisonOpenChange}
              />
              {distanceToNextMeters !== undefined && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">
                    Distance to next stop
                  </span>
                  <span className="font-medium">
                    {formatMetersAsMiles(distanceToNextMeters)}
                  </span>
                </div>
              )}
              {rangeMiles !== undefined && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Range on fuel</span>
                  <span className="font-medium">{formatMiles(rangeMiles)}</span>
                </div>
              )}
              {rangeWithoutReserveMiles !== undefined && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">
                    Range without reserve
                  </span>
                  <span className="font-medium">
                    {formatMiles(rangeWithoutReserveMiles)}
                  </span>
                </div>
              )}
              {distanceToDestinationMeters !== undefined && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">
                    Distance to destination
                  </span>
                  <span className="font-medium">
                    {formatMetersAsMiles(distanceToDestinationMeters)}
                  </span>
                </div>
              )}
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
                {summary && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        Total fuel purchased
                      </span>
                      <span className="font-medium">
                        {formatGallons(
                          Number(summary.total_fuel_purchased_gallons),
                        )}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        Total fuel cost
                      </span>
                      <span className="font-medium">
                        {formatMoney(Number(summary.total_fuel_cost))}
                      </span>
                    </div>
                  </>
                )}
              </div>
            )}
          {activeStep.isFailurePoint && activeStep.status === "reached" && (
            <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
              Last reachable point; the algorithm could not continue beyond
              here.
            </div>
          )}
        </div>
      )}

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
