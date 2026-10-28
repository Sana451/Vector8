import { describe, expect, it } from "vitest"

import {
  buildGoogleMapsLegs,
  buildHereWeGoUrl,
  chunkPoints,
  type NavigatorPoint,
} from "@/lib/navigatorLinks"

function makePoints(count: number): NavigatorPoint[] {
  return Array.from({ length: count }, (_, index) => ({
    label: `Stop ${index}`,
    coordinate: [-97 - index, 33 + index] as [number, number],
  }))
}

describe("chunkPoints", () => {
  it("returns nothing when there is no route to navigate", () => {
    expect(chunkPoints(makePoints(1))).toEqual([])
  })

  it("keeps a short trip in a single chunk", () => {
    const chunks = chunkPoints(makePoints(6), 8)

    expect(chunks).toHaveLength(1)
    expect(chunks[0]).toHaveLength(6)
  })

  it("splits a long trip into chunks of the allowed size", () => {
    const chunks = chunkPoints(makePoints(25), 8)

    expect(chunks.length).toBeGreaterThan(1)
    for (const chunk of chunks) {
      expect(chunk.length).toBeLessThanOrEqual(10)
    }
  })

  it("overlaps chunks so the next leg starts where the previous ended", () => {
    const chunks = chunkPoints(makePoints(25), 8)

    for (let index = 1; index < chunks.length; index++) {
      const previous = chunks[index - 1]
      expect(chunks[index][0]).toEqual(previous[previous.length - 1])
    }
  })

  it("covers every point across the chunks", () => {
    const points = makePoints(25)

    const chunks = chunkPoints(points, 8)

    expect(chunks[0][0]).toEqual(points[0])
    const last = chunks[chunks.length - 1]
    expect(last[last.length - 1]).toEqual(points[points.length - 1])
  })

  it("rejects a waypoint cap below one", () => {
    expect(() => chunkPoints(makePoints(5), 0)).toThrow()
  })
})

describe("buildGoogleMapsLegs", () => {
  it("uses latitude,longitude order", () => {
    const [leg] = buildGoogleMapsLegs(makePoints(2))

    expect(leg.url).toContain("origin=33%2C-97")
  })

  it("includes the intermediate stops as waypoints", () => {
    const [leg] = buildGoogleMapsLegs(makePoints(4))

    expect(leg.waypoints).toHaveLength(2)
    expect(leg.url).toContain("waypoints=")
  })

  it("omits the waypoints parameter when there are none", () => {
    const [leg] = buildGoogleMapsLegs(makePoints(2))

    expect(leg.url).not.toContain("waypoints=")
  })

  it("numbers the legs from one", () => {
    const legs = buildGoogleMapsLegs(makePoints(25), 8)

    expect(legs.map((leg) => leg.index)).toEqual(
      legs.map((_, index) => index + 1),
    )
  })

  it("returns nothing for a trip without a destination", () => {
    expect(buildGoogleMapsLegs(makePoints(1))).toEqual([])
  })
})

describe("buildHereWeGoUrl", () => {
  it("joins the points into a drive path", () => {
    const url = buildHereWeGoUrl(makePoints(3))

    expect(url).toContain("/directions/drive/")
    expect(url?.split("/").pop()).toContain("35,-99")
  })

  it("escapes labels", () => {
    const url = buildHereWeGoUrl([
      { label: "Love's #200", coordinate: [-97, 33] },
      { label: "End", coordinate: [-98, 34] },
    ])

    expect(url).toContain("%23200")
  })

  it("returns null when there is nothing to navigate", () => {
    expect(buildHereWeGoUrl(makePoints(1))).toBeNull()
  })
})
