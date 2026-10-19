/**
 * StopSelectionDetails
 *
 * Explains why the optimizer picked a station: the sticker price next to the
 * effective price, what makes up the difference (detour fuel, stop time, fixed
 * cost), and the nearby stations that lost, with the reason for each.
 * All numbers come from the backend; this component only renders them.
 */

import { ChevronDown, ChevronUp } from "lucide-react"
import { useEffect, useState } from "react"
import type {
  FuelOptimizationAlternativePublic,
  FuelOptimizationEconomicsPublic,
  FuelOptimizationLookaheadPublic,
  FuelOptimizationSelectionPublic,
} from "@/client"

interface StopSelectionDetailsProps {
  selection?: FuelOptimizationSelectionPublic
  lookahead?: FuelOptimizationLookaheadPublic
  economics?: FuelOptimizationEconomicsPublic | null
  /** Reports whether the explanation block is expanded (to highlight stations on the map). */
  onOpenChange?: (open: boolean) => void
  /** Called with [lng, lat] when a compared station is clicked. */
  onFocusStation?: (coordinate: [number, number]) => void
}

function money(value: string | number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—"
  const parsed = Number(value)
  return Number.isNaN(parsed) ? "—" : `$${parsed.toFixed(digits)}`
}

function signedPrice(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—"
  const parsed = Number(value)
  if (Number.isNaN(parsed)) return "—"
  return `${parsed >= 0 ? "+" : "−"}$${Math.abs(parsed).toFixed(3)}`
}

function km(meters: string): string {
  return `${(Number(meters) / 1000).toFixed(1)} km`
}

const OUTCOME_LABELS: Record<
  FuelOptimizationAlternativePublic["outcome"],
  string
> = {
  higher_effective_price: "Costs more per gallon once detour and time count",
  tie_broken_by_distance: "Same effective price; the farther one was preferred",
  no_fuel_to_buy: "Nothing to buy there",
  not_reachable: "Cheaper, but out of reach on the current fuel",
  overhead_exceeds_savings: "Savings do not cover the cost of the extra stop",
  nearer_cheaper_station_chosen:
    "Also cheaper than the previous station, but a nearer one was taken",
  not_cheaper_than_previous: "Not cheaper than the previous station",
}

function isEconomicsNeutral(
  economics: FuelOptimizationEconomicsPublic | null | undefined,
): boolean {
  if (!economics) return false
  return (
    Number(economics.downtime_cost_per_hour) === 0 &&
    Number(economics.fixed_stop_cost) === 0
  )
}

function Row({
  label,
  value,
  emphasized = false,
}: {
  label: string
  value: string
  emphasized?: boolean
}) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={emphasized ? "font-semibold" : "font-medium"}>
        {value}
      </span>
    </div>
  )
}

function Headline({
  selection,
}: {
  selection: FuelOptimizationSelectionPublic
}) {
  if (selection.rule === "cheaper_ahead_pays_off") {
    if (selection.next_stop_mandatory) {
      return (
        <div className="text-muted-foreground">
          A full tank does not reach the destination, so another stop was
          unavoidable. This is the nearest station cheaper than the previous
          one: filling here instead of there saves{" "}
          {money(selection.estimated_savings)}.
        </div>
      )
    }
    return (
      <div className="text-muted-foreground">
        A cheaper station that was worth the extra stop: saves{" "}
        {money(selection.estimated_savings)} against{" "}
        {money(selection.stop_overhead_cost)} of stop cost.
      </div>
    )
  }
  const premium = Number(selection.premium_per_gallon ?? 0)
  const hasCheaperAlternative = (selection.alternatives ?? []).some(
    (alternative) => alternative.cheaper_by_sticker,
  )
  if (hasCheaperAlternative && premium > 0) {
    return (
      <div className="text-muted-foreground">
        Chosen despite cheaper stations nearby: after detour and stop cost it is
        the lowest effective price.
      </div>
    )
  }
  return (
    <div className="text-muted-foreground">
      Lowest effective price per gallon among the stations in reach.
    </div>
  )
}

export function StopSelectionDetails({
  selection,
  lookahead,
  economics,
  onOpenChange,
  onFocusStation,
}: StopSelectionDetailsProps) {
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    onOpenChange?.(isOpen)
    return () => onOpenChange?.(false)
  }, [isOpen, onOpenChange])

  if (!selection && !lookahead) return null

  const alternatives = selection?.alternatives ?? []

  return (
    <div className="mt-3 border-t pt-2 text-xs space-y-2">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
        className="flex w-full items-center justify-between font-semibold"
      >
        <span>Why this station</span>
        {isOpen ? (
          <ChevronUp className="h-4 w-4" />
        ) : (
          <ChevronDown className="h-4 w-4" />
        )}
      </button>
      {isOpen && selection && (
        <div className="space-y-1">
          <Headline selection={selection} />
          <Row
            label="Sticker price"
            value={`${money(selection.sticker_price_per_gallon, 3)}/gal`}
          />
          {selection.effective_price_per_gallon != null && (
            <Row
              label="Effective price"
              value={`${money(selection.effective_price_per_gallon, 3)}/gal`}
              emphasized
            />
          )}
          {selection.premium_per_gallon != null && (
            <Row
              label="Premium over sticker"
              value={`${signedPrice(selection.premium_per_gallon)}/gal`}
            />
          )}
          <Row
            label="Detour fuel"
            value={`${money(selection.detour_fuel_cost)} (${Number(
              selection.detour_fuel_gallons,
            ).toFixed(2)} gal)`}
          />
          <Row label="Stop time" value={money(selection.time_cost)} />
          {Number(selection.fixed_stop_cost) > 0 && (
            <Row
              label="Fixed stop cost"
              value={money(selection.fixed_stop_cost)}
            />
          )}
          {selection.rule === "cheaper_ahead_pays_off" && (
            <>
              <Row
                label="Estimated savings"
                value={money(selection.estimated_savings)}
              />
              {!selection.next_stop_mandatory && (
                <Row
                  label="Extra stop cost"
                  value={money(selection.stop_overhead_cost)}
                />
              )}
            </>
          )}
          {economics && isEconomicsNeutral(economics) && (
            <div className="text-muted-foreground">
              Stop time is not priced (downtime cost is 0); only detour fuel
              counts.
            </div>
          )}
        </div>
      )}

      {isOpen && alternatives.length > 0 && (
        <div className="space-y-1">
          <div className="font-semibold">
            Compared with ({alternatives.length})
          </div>
          <div className="max-h-64 space-y-1 overflow-y-auto pr-1">
            {alternatives.map((alternative) => (
              <button
                type="button"
                key={alternative.station_id}
                onClick={() =>
                  onFocusStation?.([
                    Number(alternative.longitude),
                    Number(alternative.latitude),
                  ])
                }
                title="Show on map"
                className="block w-full cursor-pointer rounded border px-2 py-1 text-left space-y-0.5 hover:bg-muted"
              >
                <div className="flex justify-between gap-2">
                  <span className="font-medium truncate">
                    {alternative.name || "Station"}
                  </span>
                  <span>
                    {money(alternative.fuel_price_per_gallon, 3)}
                    {alternative.cheaper_by_sticker && (
                      <span className="text-emerald-600 dark:text-emerald-400">
                        {" "}
                        cheaper
                      </span>
                    )}
                  </span>
                </div>
                <div className="text-muted-foreground">
                  Detour {km(alternative.detour_distance_meters)} /{" "}
                  {Math.round(alternative.detour_time_seconds / 60)} min
                  {alternative.effective_price_per_gallon != null &&
                    ` · effective ${money(alternative.effective_price_per_gallon, 3)}` +
                      (alternative.delta_vs_chosen_per_gallon != null
                        ? ` (${signedPrice(alternative.delta_vs_chosen_per_gallon)})`
                        : "")}
                </div>
                <div>
                  {OUTCOME_LABELS[alternative.outcome]}
                  {alternative.estimated_savings != null &&
                    alternative.stop_overhead_cost != null &&
                    ` (${money(alternative.estimated_savings)} vs ${money(alternative.stop_overhead_cost)})`}
                </div>
                {alternative.total_extra_cost != null && (
                  <div className="text-amber-600 dark:text-amber-400">
                    {`${signedPrice(alternative.total_extra_cost)} more for this fill`}
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {isOpen && selection && alternatives.length === 0 && (
        <div className="text-muted-foreground">
          No other stations were within reach of a full tank to compare with.
        </div>
      )}

      {isOpen && lookahead && lookahead.rule === "cheaper_ahead_rejected" && (
        <div className="text-muted-foreground">
          Filled up here: {lookahead.station_name || "a cheaper station ahead"}{" "}
          saves {money(lookahead.estimated_savings)} but the extra stop costs{" "}
          {money(lookahead.stop_overhead_cost)}.
        </div>
      )}
      {isOpen && lookahead && lookahead.rule === "cheaper_ahead_pays_off" && (
        <div className="text-muted-foreground">
          Buying only what is needed to reach{" "}
          {lookahead.station_name || "a cheaper station ahead"} (
          {money(lookahead.price_difference_per_gallon, 3)}/gal cheaper).
        </div>
      )}
    </div>
  )
}
