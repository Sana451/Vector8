/**
 * Deep links that open a trip in a phone navigator.
 *
 * Google Maps caps a single directions URL at a handful of intermediate
 * waypoints, so a trip with many fuel stops is split into several consecutive
 * legs: each leg starts where the previous one ended, and following them in
 * order reproduces the whole trip.
 */

/** Intermediate waypoints Google Maps accepts in one directions URL. */
export const GOOGLE_MAPS_MAX_WAYPOINTS = 8

export interface NavigatorPoint {
  label: string
  /** GeoJSON order: `[longitude, latitude]`. */
  coordinate: [number, number]
}

export interface NavigatorLeg {
  /** 1-based index of the leg, for labelling buttons. */
  index: number
  origin: NavigatorPoint
  destination: NavigatorPoint
  waypoints: NavigatorPoint[]
  url: string
}

function latLon(point: NavigatorPoint): string {
  const [longitude, latitude] = point.coordinate
  return `${latitude},${longitude}`
}

/**
 * Split points into chunks that each fit one Google Maps directions URL.
 *
 * Consecutive chunks overlap by one point so the next leg starts exactly where
 * the previous one ended.
 */
export function chunkPoints(
  points: NavigatorPoint[],
  maxWaypoints: number = GOOGLE_MAPS_MAX_WAYPOINTS,
): NavigatorPoint[][] {
  if (maxWaypoints < 1) {
    throw new Error("maxWaypoints must be at least 1")
  }
  if (points.length < 2) {
    return []
  }

  const perChunk = maxWaypoints + 2
  const chunks: NavigatorPoint[][] = []
  let start = 0

  while (start < points.length - 1) {
    chunks.push(points.slice(start, start + perChunk))
    start += perChunk - 1
  }

  return chunks
}

/**
 * Build Google Maps directions links covering every point in order.
 *
 * Returns an empty list when there is nothing to navigate (fewer than two
 * points), which the UI uses to hide the buttons entirely.
 */
export function buildGoogleMapsLegs(
  points: NavigatorPoint[],
  maxWaypoints: number = GOOGLE_MAPS_MAX_WAYPOINTS,
): NavigatorLeg[] {
  return chunkPoints(points, maxWaypoints).map((chunk, index) => {
    const origin = chunk[0]
    const destination = chunk[chunk.length - 1]
    const waypoints = chunk.slice(1, -1)

    const params = new URLSearchParams({
      api: "1",
      origin: latLon(origin),
      destination: latLon(destination),
      travelmode: "driving",
    })
    if (waypoints.length > 0) {
      params.set("waypoints", waypoints.map(latLon).join("|"))
    }

    return {
      index: index + 1,
      origin,
      destination,
      waypoints,
      url: `https://www.google.com/maps/dir/?${params.toString()}`,
    }
  })
}

/**
 * Build a HERE WeGo link for the whole trip.
 *
 * HERE WeGo takes the route as a slash-separated path and does not impose the
 * same tight waypoint cap, so one link is enough.
 */
export function buildHereWeGoUrl(points: NavigatorPoint[]): string | null {
  if (points.length < 2) {
    return null
  }

  const path = points
    .map((point) => `${latLon(point)},${encodeURIComponent(point.label)}`)
    .join("/")

  return `https://wego.here.com/directions/drive/${path}`
}
