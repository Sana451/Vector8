import type { VehicleConstraintsInfo, VehiclePublic } from "@/client"

export const RECOMMENDED_ROUTING_FIELDS = [
  { key: "height_in", label: "height" },
  { key: "width_in", label: "width" },
  { key: "length_in", label: "length" },
  { key: "gross_weight_lbs", label: "gross weight" },
] as const

const BACKEND_FIELD_LABELS: Record<string, string> = {
  height: "height",
  width: "width",
  length: "length",
  gross_weight: "gross weight",
}

/** Labels of the recommended dimension/weight fields a vehicle does not have. */
export function getMissingRoutingFields(
  vehicle: Pick<
    VehiclePublic,
    (typeof RECOMMENDED_ROUTING_FIELDS)[number]["key"]
  >,
): string[] {
  return RECOMMENDED_ROUTING_FIELDS.filter(
    ({ key }) => vehicle[key] === null || vehicle[key] === undefined,
  ).map(({ label }) => label)
}

export function labelsFromBackendFields(fields: string[]): string[] {
  return fields.map((field) => BACKEND_FIELD_LABELS[field] ?? field)
}

export type VehicleConstraintsWarning = {
  missing: string[]
  allMissing: boolean
}

/** Warning shown when constraints are enabled but the vehicle lacks data. */
export function getVehicleConstraintsWarning(
  missing: string[],
): VehicleConstraintsWarning | null {
  if (missing.length === 0) return null
  return {
    missing,
    allMissing: missing.length === RECOMMENDED_ROUTING_FIELDS.length,
  }
}

const formatFeetInches = (inches: number) =>
  `${Math.floor(inches / 12)}'${inches % 12}"`

/** Short human readable summary of a vehicle's routing dimensions. */
export function formatRoutingSummary(
  vehicle: Pick<
    VehiclePublic,
    "height_in" | "width_in" | "length_in" | "gross_weight_lbs"
  >,
): string | null {
  const parts: string[] = []
  if (vehicle.height_in) parts.push(`H ${formatFeetInches(vehicle.height_in)}`)
  if (vehicle.width_in) parts.push(`W ${formatFeetInches(vehicle.width_in)}`)
  if (vehicle.length_in) parts.push(`L ${formatFeetInches(vehicle.length_in)}`)
  if (vehicle.gross_weight_lbs) {
    parts.push(`GVWR ${vehicle.gross_weight_lbs.toLocaleString("en-US")} lb`)
  }
  return parts.length > 0 ? parts.join(" · ") : null
}

export function describeAppliedConstraints(
  info: VehicleConstraintsInfo | null | undefined,
): { warning: VehicleConstraintsWarning | null; sentCount: number } | null {
  if (!info) return null
  return {
    warning: getVehicleConstraintsWarning(
      labelsFromBackendFields(info.missing_fields ?? []),
    ),
    sentCount: Object.keys(info.sent_parameters ?? {}).length,
  }
}
