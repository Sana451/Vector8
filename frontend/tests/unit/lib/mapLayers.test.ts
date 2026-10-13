import booleanPointInPolygon from "@turf/boolean-point-in-polygon"
import { describe, expect, it } from "vitest"
import type { MapOverviewResponse } from "@/client/types.gen"
import {
  buildDetourFeature,
  buildFuelFeatures,
  buildRestAreaFeatures,
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

describe("buildRestAreaFeatures", () => {
  it("should build a FeatureCollection with popup-friendly properties", () => {
    const result = buildRestAreaFeatures({
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          id: "here:pds:place:840dr5ru-456",
          geometry: {
            type: "Point",
            coordinates: [-87.87654, 41.95012],
          },
          properties: {
            provider: "here",
            provider_place_id: "here:pds:place:840dr5ru-456",
            title: "O'Hare Oasis Travel Plaza",
            categories: [
              { id: "700-7900-0131", name: "Truck Parking", primary: true },
              { id: "400-4300-0199", name: "Complete Rest Area" },
            ],
            distance_meters: 22550,
            address: {
              label:
                "I-294 Milepost 38, Schiller Park, IL 60176, United States",
            },
            access_points: [
              { type: "Point", coordinates: [-87.87611, 41.95022] },
            ],
            opening_hours: [{ text: ["Mon-Sun: 00:00 - 23:59"] }],
            contacts: [{ phone: [{ value: "+13125550123" }] }],
            chains: [],
            references: [],
            metadata: { ontologyId: "here:cm:ontology:rest_area" },
          },
        },
      ],
    })

    expect(result?.type).toBe("FeatureCollection")
    expect(result?.features).toHaveLength(1)
    expect(result?.features[0].properties?.primaryCategoryId).toBe(
      "700-7900-0131",
    )
    expect(result?.features[0].properties?.addressLabel).toContain(
      "Schiller Park",
    )
    expect(result?.features[0].properties?.contactsSummary).toContain(
      "+13125550123",
    )
    expect(result?.features[0].properties?.categoryLabels).toBe(
      "Truck Parking, Complete Rest Area",
    )
    expect(result?.features[0].properties?.categoryIds).toBe(
      "700-7900-0131,400-4300-0199",
    )

    for (const value of Object.values(result?.features[0].properties ?? {})) {
      expect(Array.isArray(value)).toBe(false)
      expect(typeof value === "object" && value !== null).toBe(false)
    }
  })

  it("should return null for an empty FeatureCollection", () => {
    expect(
      buildRestAreaFeatures({ type: "FeatureCollection", features: [] }),
    ).toBeNull()
  })

  it("should skip malformed rest area features and keep valid ones", () => {
    const malformedPayload: unknown = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          id: "invalid-coordinates",
          geometry: {
            type: "Point",
            coordinates: [Number.NaN, 41.95],
          },
          properties: {
            provider: "here",
            provider_place_id: "invalid-coordinates",
            title: "Broken coordinates",
          },
        },
        {
          type: "Feature",
          id: "invalid-properties",
          geometry: {
            type: "Point",
            coordinates: [-87.8, 41.95],
          },
          properties: {
            provider: "here",
            provider_place_id: 42 as unknown as string,
            title: "Broken properties",
          },
        },
        {
          type: "Feature",
          id: "valid",
          geometry: {
            type: "Point",
            coordinates: [-87.87654, 41.95012],
          },
          properties: {
            provider: "here",
            provider_place_id: "valid",
            title: "Valid rest area",
            categories: [{ id: "700-7900-0131", name: "Truck Parking" }],
          },
        },
      ],
    }

    const result = buildRestAreaFeatures(malformedPayload as never)

    expect(result?.features).toHaveLength(1)
    expect(result?.features[0].id).toBe("valid")
    expect(result?.features[0].properties?.providerPlaceId).toBe("valid")
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
      rest_areas: { type: "FeatureCollection", features: [] },
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
      rest_areas: { type: "FeatureCollection", features: [] },
    }

    expect(extractOverviewCoordinates(response)).toBeNull()
  })
})

describe("buildDetourFeature", () => {
  const route: Coordinate[] = [
    [-100, 40],
    [-99, 40],
    [-98, 40],
  ]

  it("returns null for fewer than two points", () => {
    expect(buildDetourFeature([[-100, 40]], 10)).toBeNull()
    expect(buildDetourFeature(null, 10)).toBeNull()
  })

  it("keeps the zone beside the route but cuts the caps before start and after finish", () => {
    const feature = buildDetourFeature(route, 10)
    if (!feature) throw new Error("expected a feature")
    const contains = (point: number[]) =>
      booleanPointInPolygon(point, feature as never)

    expect(contains([-99, 40.05])).toBe(true)
    expect(contains([-99.99, 40.05])).toBe(true)
    expect(contains([-98.01, 39.95])).toBe(true)
    expect(contains([-100.05, 40])).toBe(false)
    expect(contains([-97.95, 40])).toBe(false)
  })

  it("cuts perpendicular to the overall heading when the first segment points elsewhere", () => {
    const feature = buildDetourFeature(
      [
        [-100, 40],
        [-100, 40.02],
        [-100.05, 40.02],
        [-101, 40.02],
      ],
      10,
    )
    if (!feature) throw new Error("expected a feature")
    const contains = (point: number[]) =>
      booleanPointInPolygon(point, feature as never)

    expect(contains([-100, 40.01])).toBe(true)
    expect(contains([-99.95, 40.01])).toBe(false)
  })
})
