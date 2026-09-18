import { describe, expect, it } from "vitest"
import type { CalculateRouteResponse } from "@/client"
import type { Coordinate } from "@/lib/routing"
import { calculateBoundingBox, extractRouteCoordinates } from "@/lib/routing"

describe("extractRouteCoordinates", () => {
  it("should extract coordinates from valid response", () => {
    const response: CalculateRouteResponse = {
      routes: [
        {
          summary: {
            lengthInMeters: 1000,
            travelDurationInSeconds: 60,
          },
          legs: [
            {
              summary: {
                lengthInMeters: 1000,
                travelDurationInSeconds: 60,
              },
              path: {
                type: "LineString",
                coordinates: [
                  [-74.006, 40.7128],
                  [-74.001, 40.715],
                  [-73.995, 40.72],
                ],
              },
            },
          ],
        },
      ],
    }

    const result = extractRouteCoordinates(response)

    expect(result).toEqual([
      [-74.006, 40.7128],
      [-74.001, 40.715],
      [-73.995, 40.72],
    ])
  })

  it("should return null when routes array is empty", () => {
    const response: CalculateRouteResponse = {
      routes: [],
    }

    const result = extractRouteCoordinates(response)

    expect(result).toBeNull()
  })

  it("should return null when legs array is empty", () => {
    const response: CalculateRouteResponse = {
      routes: [
        {
          summary: {
            lengthInMeters: 1000,
            travelDurationInSeconds: 60,
          },
          legs: [],
        },
      ],
    }

    const result = extractRouteCoordinates(response)

    expect(result).toBeNull()
  })

  it("should return null when path is missing", () => {
    const response: CalculateRouteResponse = {
      routes: [
        {
          summary: {
            lengthInMeters: 1000,
            travelDurationInSeconds: 60,
          },
          legs: [
            {
              summary: {
                lengthInMeters: 1000,
                travelDurationInSeconds: 60,
              },
            },
          ],
        },
      ],
    }

    const result = extractRouteCoordinates(response)

    expect(result).toBeNull()
  })

  it("should return null when coordinates have less than 2 points", () => {
    const response: CalculateRouteResponse = {
      routes: [
        {
          summary: {
            lengthInMeters: 1000,
            travelDurationInSeconds: 60,
          },
          legs: [
            {
              summary: {
                lengthInMeters: 1000,
                travelDurationInSeconds: 60,
              },
              path: {
                type: "LineString",
                coordinates: [[-74.006, 40.7128]],
              },
            },
          ],
        },
      ],
    }

    const result = extractRouteCoordinates(response)

    expect(result).toBeNull()
  })
})

describe("calculateBoundingBox", () => {
  it("should calculate correct bounding box", () => {
    const coordinates: Coordinate[] = [
      [-74.006, 40.7128],
      [-74.001, 40.715],
      [-73.995, 40.72],
    ]

    const result = calculateBoundingBox(coordinates)

    expect(result).toEqual([-74.006, 40.7128, -73.995, 40.72])
  })

  it("should handle single coordinate", () => {
    const coordinates: Coordinate[] = [[-74.006, 40.7128]]

    const result = calculateBoundingBox(coordinates)

    expect(result).toEqual([-74.006, 40.7128, -74.006, 40.7128])
  })

  it("should handle coordinates in any order", () => {
    const coordinates: Coordinate[] = [
      [0, 0],
      [-5, 5],
      [10, -3],
      [3, 8],
    ]

    const result = calculateBoundingBox(coordinates)

    expect(result).toEqual([-5, -3, 10, 8])
  })
})
