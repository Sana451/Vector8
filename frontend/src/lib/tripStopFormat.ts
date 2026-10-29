type DecimalLike = string | number | null | undefined

export function parseDecimal(value: DecimalLike): number | null {
  if (value === null || value === undefined || value === "") return null
  const parsed = Number(value)
  return Number.isNaN(parsed) ? null : parsed
}

export function formatTripGallons(value: DecimalLike): string {
  const gallons = parseDecimal(value)
  return gallons === null ? "—" : `${gallons.toFixed(1)} gal`
}

export function formatTripMoney(value: DecimalLike): string {
  const amount = parseDecimal(value)
  return amount === null ? "—" : `$${amount.toFixed(2)}`
}

export function formatTripDetour(
  meters: DecimalLike,
  seconds: number | null | undefined,
): string {
  const distance = parseDecimal(meters)
  if (distance === null) return "—"
  const km = `${(distance / 1000).toFixed(1)} km`
  if (seconds === null || seconds === undefined) return km
  return `${km} / ${Math.round(seconds / 60)} min`
}

/** Matches the optimizer walkthrough: the tank counts as full when refuelled to usable capacity. */
export function isTankFullAfterRefuel(
  fuelAfter: DecimalLike,
  usableTankGallons: DecimalLike,
): boolean {
  const after = parseDecimal(fuelAfter)
  const usable = parseDecimal(usableTankGallons)
  if (after === null || usable === null || usable <= 0) return false
  return Math.abs(after - usable) < 0.05
}
