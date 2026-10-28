import { describe, expect, it } from "vitest"

import {
  formatDateTime,
  formatDelta,
  formatDuration,
  formatMiles,
  TRIP_STATUS_CLASSES,
  TRIP_STATUS_LABELS,
} from "@/lib/tripPlans"

describe("formatMiles", () => {
  it("converts meters to miles", () => {
    expect(formatMiles(1609.344)).toBe("1.0 mi")
    expect(formatMiles(16093.44)).toBe("10.0 mi")
  })

  it("renders a dash for missing values", () => {
    expect(formatMiles(null)).toBe("—")
    expect(formatMiles(undefined)).toBe("—")
  })
})

describe("formatDuration", () => {
  it("shows minutes only below an hour", () => {
    expect(formatDuration(1500)).toBe("25 min")
  })

  it("shows hours and minutes", () => {
    expect(formatDuration(3600 * 2 + 60 * 5)).toBe("2 h 5 min")
  })

  it("renders a dash for missing values", () => {
    expect(formatDuration(null)).toBe("—")
  })
})

describe("formatDateTime", () => {
  it("renders a dash for empty input", () => {
    expect(formatDateTime(null)).toBe("—")
    expect(formatDateTime("")).toBe("—")
  })

  it("formats a valid timestamp", () => {
    expect(formatDateTime("2024-05-01T12:00:00Z")).not.toBe("—")
  })
})

describe("formatDelta", () => {
  const miles = (value: number) => `${value} mi`

  it("marks extra driving with a plus", () => {
    expect(formatDelta(12, miles)).toBe("+12 mi")
  })

  it("marks savings with a minus and formats the magnitude", () => {
    expect(formatDelta(-3, miles)).toBe("−3 mi")
  })

  it("uses plus-minus for no change", () => {
    expect(formatDelta(0, miles)).toBe("±0 mi")
  })
})

describe("trip status maps", () => {
  it("cover the same statuses", () => {
    expect(Object.keys(TRIP_STATUS_CLASSES).sort()).toEqual(
      Object.keys(TRIP_STATUS_LABELS).sort(),
    )
  })
})
