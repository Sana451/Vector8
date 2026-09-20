import { describe, expect, it } from "vitest"
import type { GeoJSONPoint } from "@/client"
import {
  buildMapPointFromAddress,
  buildMapPointFromLocation,
  buildRouteOverviewRequest,
  createAddressSelection,
} from "@/lib/mapRequest"

describe("mapRequest helpers", () => {
  it("serializes MapPointInput from address", () => {
    expect(
      buildMapPointFromAddress("1521 Hickory Trail Allen TX 75002"),
    ).toEqual({
      address: "1521 Hickory Trail Allen TX 75002",
    })
  })

  it("serializes MapPointInput from coordinates", () => {
    const location: GeoJSONPoint = {
      type: "Point",
      coordinates: [-96.6705, 33.1032],
    }

    expect(buildMapPointFromLocation(location)).toEqual({ location })
  })

  it("builds a mixed route-overview request", () => {
    const request = buildRouteOverviewRequest({
      pickup: buildMapPointFromAddress("1521 Hickory Trail Allen TX 75002"),
      delivery: buildMapPointFromLocation({
        type: "Point",
        coordinates: [-123.0463, 44.086],
      }),
      layers: ["route", "traffic"],
    })

    expect(request).toEqual({
      pickup: { address: "1521 Hickory Trail Allen TX 75002" },
      delivery: {
        location: {
          type: "Point",
          coordinates: [-123.0463, 44.086],
        },
      },
      layers: ["route", "traffic"],
    })
  })

  it("stores the selected autocomplete result", () => {
    const selection = createAddressSelection("1521 Hickory", {
      formatted_address: "1521 Hickory Trail, Allen, TX 75002",
      location: {
        type: "Point",
        coordinates: [-96.6705, 33.1032],
      },
    })

    expect(selection).toEqual({
      query: "1521 Hickory",
      formatted_address: "1521 Hickory Trail, Allen, TX 75002",
      location: {
        type: "Point",
        coordinates: [-96.6705, 33.1032],
      },
    })
  })
})
