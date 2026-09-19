import { describe, expect, it } from "vitest"
import type { MapOverviewResponse } from "@/client"
import {
  buildFuelFeatures,
  buildRouteFeature,
  buildTrafficFeatures,
  buildTruckRestrictionFeatures,
  extractOverviewCoordinates,
} from "@/lib/mapLayers"
import type { Coordinate } from "@/lib/routing"

describe("buildRouteFeature", () => {
  it("should build a LineString feature from coordinates", () => {
    const coordinates: Coordinate[] = [
      [-74.006, 40.7128],
      [-73.9855, 40.758],
    ]

    const result = buildRouteFeature(coordinates)

    expect(result).toEqual({
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates },
    })
  })

  it("should return null for null coordinates", () => {
    expect(buildRouteFeature(null)).toBeNull()
  })

  it("should return null when fewer than 2 points", () => {
    expect(buildRouteFeature([[-74.006, 40.7128]])).toBeNull()
  })
})

describe("buildFuelFeatures", () => {
  it("should build a FeatureCollection from stations", () => {
    const result = buildFuelFeatures([
      {
        external_id: "s1",
        name: "Pilot",
        brand: "Pilot Flying J",
        location: { type: "Point", coordinates: [-74.0, 40.72] },
        diesel_price: 3.79,
        truck_accessible: true,
      },
    ])

    expect(result?.type).toBe("FeatureCollection")
    expect(result?.features).toHaveLength(1)
    expect(result?.features[0].geometry).toEqual({
      type: "Point",
      coordinates: [-74.0, 40.72],
    })
    expect(result?.features[0].properties?.dieselPrice).toBe(3.79)
  })

  it("should return null for an empty list", () => {
    expect(buildFuelFeatures([])).toBeNull()
  })

  it("should return null when undefined", () => {
    expect(buildFuelFeatures(undefined)).toBeNull()
  })
})

describe("buildTruckRestrictionFeatures", () => {
  it("should build a FeatureCollection from restrictions", () => {
    const result = buildTruckRestrictionFeatures([
      {
        external_id: "r1",
        restriction_type: "bridge_height",
        description: "Low bridge",
        location: { type: "Point", coordinates: [-74.01, 40.73] },
        max_height_cm: 410,
      },
    ])

    expect(result?.features).toHaveLength(1)
    expect(result?.features[0].properties?.restrictionType).toBe(
      "bridge_height",
    )
    expect(result?.features[0].properties?.maxHeightCm).toBe(410)
  })

  it("should return null for an empty list", () => {
    expect(buildTruckRestrictionFeatures([])).toBeNull()
  })
})

describe("buildTrafficFeatures", () => {
  it("should build a FeatureCollection from incidents with location", () => {
    const result = buildTrafficFeatures({
      provider: "tomtom",
      incidents: [
        {
          external_id: "i1",
          severity: "major",
          location: { type: "Point", coordinates: [-74.0, 40.74] },
          delay_seconds: 300,
        },
      ],
    })

    expect(result?.features).toHaveLength(1)
    expect(result?.features[0].properties?.severity).toBe("major")
  })

  it("should skip incidents without location", () => {
    const result = buildTrafficFeatures({
      provider: "tomtom",
      incidents: [{ external_id: "i1", severity: "minor" }],
    })

    expect(result).toBeNull()
  })

  it("should return null when traffic is null", () => {
    expect(buildTrafficFeatures(null)).toBeNull()
  })

  it("should return null when there are no incidents", () => {
    expect(
      buildTrafficFeatures({ provider: "tomtom", incidents: [] }),
    ).toBeNull()
  })
})

describe("extractOverviewCoordinates", () => {
  it("should concatenate coordinates across legs", () => {
    const response: MapOverviewResponse = {
      route: {
        provider: "tomtom",
        routes: [
          {
            summary: { lengthInMeters: 100, travelDurationInSeconds: 10 },
            legs: [
              {
                summary: { lengthInMeters: 50, travelDurationInSeconds: 5 },
                path: {
                  type: "LineString",
                  coordinates: [
                    [-74.006, 40.7128],
                    [-74.001, 40.715],
                  ],
                },
              },
              {
                summary: { lengthInMeters: 50, travelDurationInSeconds: 5 },
                path: {
                  type: "LineString",
                  coordinates: [
                    [-74.001, 40.715],
                    [-73.995, 40.72],
                  ],
                },
              },
            ],
          },
        ],
      },
    }

    expect(extractOverviewCoordinates(response)).toEqual([
      [-74.006, 40.7128],
      [-74.001, 40.715],
      [-74.001, 40.715],
      [-73.995, 40.72],
    ])
  })

  it("should return null when route layer is missing", () => {
    expect(extractOverviewCoordinates({})).toBeNull()
  })

  it("should return null when there is no usable geometry", () => {
    const response: MapOverviewResponse = {
      route: {
        provider: "tomtom",
        routes: [
          {
            summary: { lengthInMeters: 100, travelDurationInSeconds: 10 },
          },
        ],
      },
    }

    expect(extractOverviewCoordinates(response)).toBeNull()
  })
})
