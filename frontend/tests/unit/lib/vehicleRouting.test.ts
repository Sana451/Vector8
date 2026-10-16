import { describe, expect, it } from "vitest"
import {
  describeAppliedConstraints,
  formatRoutingSummary,
  getMissingRoutingFields,
  getVehicleConstraintsWarning,
} from "@/lib/vehicleRouting"

const full = {
  height_in: 150,
  width_in: 96,
  length_in: 312,
  gross_weight_lbs: 26000,
}

describe("vehicleRouting helpers", () => {
  it("reports missing recommended fields", () => {
    expect(getMissingRoutingFields(full)).toEqual([])
    expect(
      getMissingRoutingFields({
        ...full,
        height_in: null,
        gross_weight_lbs: null,
      }),
    ).toEqual(["height", "gross weight"])
  })

  it("flags the case when nothing is set", () => {
    const missing = getMissingRoutingFields({
      height_in: null,
      width_in: null,
      length_in: null,
      gross_weight_lbs: null,
    })
    expect(getVehicleConstraintsWarning(missing)?.allMissing).toBe(true)
    expect(getVehicleConstraintsWarning([])).toBeNull()
  })

  it("formats a summary", () => {
    expect(formatRoutingSummary(full)).toBe(
      `H 12'6" · W 8'0" · L 26'0" · GVWR 26,000 lb`,
    )
    expect(
      formatRoutingSummary({
        height_in: null,
        width_in: null,
        length_in: null,
        gross_weight_lbs: null,
      }),
    ).toBeNull()
  })

  it("describes backend constraint info", () => {
    expect(describeAppliedConstraints(null)).toBeNull()
    const described = describeAppliedConstraints({
      vehicle_id: "v",
      applied: true,
      sent_parameters: { "vehicle[width]": "244" },
      missing_fields: ["height", "gross_weight"],
    })
    expect(described?.sentCount).toBe(1)
    expect(described?.warning?.missing).toEqual(["height", "gross weight"])
  })
})
