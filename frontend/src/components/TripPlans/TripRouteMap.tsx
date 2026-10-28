/**
 * TripRouteMap component
 *
 * A read-only map for a saved trip: the provider-verified route plus the
 * frozen stops. It owns its own map instance so a trip detail page does not
 * have to pull in the optimizer's interactive map.
 */

import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useEffect, useRef, useState } from "react"

import type { TripPlanDetailPublic } from "@/client"
import { RefinedRouteLayer, TripStopsLayer } from "@/components/Map/layers"
import TomTomMap, { type TomTomMapHandle } from "@/components/Map/TomTomMap"
import type { Coordinate } from "@/lib/routing"

interface TripRouteMapProps {
  trip: Pick<
    TripPlanDetailPublic,
    "stops" | "refined_geometry" | "base_geometry"
  >
  className?: string
}

/** Bounding box of a line, used to frame the whole trip on first render. */
function boundsOf(
  coordinates: Coordinate[],
): [number, number, number, number] | null {
  if (coordinates.length === 0) {
    return null
  }

  let [minLon, minLat] = coordinates[0]
  let [maxLon, maxLat] = coordinates[0]

  for (const [longitude, latitude] of coordinates) {
    minLon = Math.min(minLon, longitude)
    minLat = Math.min(minLat, latitude)
    maxLon = Math.max(maxLon, longitude)
    maxLat = Math.max(maxLat, latitude)
  }

  return [minLon, minLat, maxLon, maxLat]
}

export function TripRouteMap({ trip, className }: TripRouteMapProps) {
  const mapHandleRef = useRef<TomTomMapHandle | null>(null)
  const [mapInstance, setMapInstance] = useState<MapLibreMap | null>(null)

  const setHandle = useCallback((handle: TomTomMapHandle | null) => {
    mapHandleRef.current = handle
    setMapInstance(handle?.getMapInstance() ?? null)
  }, [])

  const geometry = trip.refined_geometry ?? trip.base_geometry
  const coordinates = geometry?.coordinates as Coordinate[] | undefined

  useEffect(() => {
    const bounds = boundsOf(coordinates ?? [])
    if (!bounds) {
      return
    }
    mapHandleRef.current?.fitBounds(bounds, 60)
  }, [coordinates])

  return (
    <div className={className}>
      <TomTomMap ref={setHandle} className="h-full w-full" />
      <RefinedRouteLayer
        mapInstance={mapInstance}
        coordinates={coordinates ?? null}
      />
      <TripStopsLayer mapInstance={mapInstance} stops={trip.stops ?? []} />
    </div>
  )
}
