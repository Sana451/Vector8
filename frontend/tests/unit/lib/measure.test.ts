import { describe, expect, it } from "vitest"
import {
  buildMeasureFeatures,
  formatDistance,
  measureLengthKm,
  shouldAddFreehandPoint,
} from "@/lib/measure"

describe("measure", () => {
  it("returns 0 for fewer than two points", () => {
    expect(measureLengthKm([])).toBe(0)
    expect(measureLengthKm([[0, 0]])).toBe(0)
  })

  it("measures ~111 km per degree of latitude", () => {
    expect(
      measureLengthKm([
        [0, 0],
        [0, 1],
      ]),
    ).toBeCloseTo(111.19, 1)
  })

  it("sums segments of a curve", () => {
    const a = measureLengthKm([
      [0, 0],
      [0, 1],
    ])
    const b = measureLengthKm([
      [0, 1],
      [1, 1],
    ])
    expect(
      measureLengthKm([
        [0, 0],
        [0, 1],
        [1, 1],
      ]),
    ).toBeCloseTo(a + b, 5)
  })

  it("formats km and miles", () => {
    expect(formatDistance(1.609344)).toBe("1.61 km (1.00 mi)")
  })

  it("builds features", () => {
    expect(buildMeasureFeatures([])).toBeNull()
    expect(
      buildMeasureFeatures([
        [0, 0],
        [1, 1],
      ])?.features,
    ).toHaveLength(3)
    expect(
      buildMeasureFeatures(
        [
          [0, 0],
          [1, 1],
        ],
        false,
      )?.features,
    ).toHaveLength(1)
  })

  it("thins freehand points", () => {
    expect(shouldAddFreehandPoint(undefined, [0, 0])).toBe(true)
    expect(shouldAddFreehandPoint([0, 0], [0.00001, 0])).toBe(false)
    expect(shouldAddFreehandPoint([0, 0], [0.01, 0])).toBe(true)
  })
})
