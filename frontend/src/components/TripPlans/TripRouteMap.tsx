/**
 * TripRouteMap component
 *
 * A read-only map for a saved trip: the provider-verified route plus the
 * frozen stops. It owns its own map instance so a trip detail page does not
 * have to pull in the optimizer's interactive map.
 */

import { Maximize, Minimize } from "lucide-react"
import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useEffect, useRef, useState } from "react"

import type { TripPlanDetailPublic } from "@/client"
import { RefinedRouteLayer, TripStopsLayer } from "@/components/Map/layers"
import TomTomMap, { type TomTomMapHandle } from "@/components/Map/TomTomMap"
import useCustomToast from "@/hooks/useCustomToast"
import type { Coordinate } from "@/lib/routing"

interface TripRouteMapProps {
  trip: Pick<
    TripPlanDetailPublic,
    "stops" | "refined_geometry" | "base_geometry"
  >
  className?: string
  /** Pans (without changing zoom) to a stop when `key` changes. */
  focusStop?: { coordinate: Coordinate; key: number } | null
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

export function TripRouteMap({
  trip,
  className,
  focusStop,
}: TripRouteMapProps) {
  const mapHandleRef = useRef<TomTomMapHandle | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [mapInstance, setMapInstance] = useState<MapLibreMap | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const { showErrorToast } = useCustomToast()

  useEffect(() => {
    const onChange = () => {
      setIsFullscreen(document.fullscreenElement === containerRef.current)
    }
    document.addEventListener("fullscreenchange", onChange)
    return () => {
      document.removeEventListener("fullscreenchange", onChange)
      if (document.fullscreenElement === containerRef.current) {
        void document.exitFullscreen()
      }
    }
  }, [])

  const toggleFullscreen = () => {
    const container = containerRef.current
    if (!container) return
    if (document.fullscreenElement === container) {
      void document.exitFullscreen()
      return
    }
    container.requestFullscreen().catch(() => {
      showErrorToast("Full screen mode is not available")
    })
  }

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

  useEffect(() => {
    const target = focusStop?.coordinate
    if (!target) {
      return
    }
    mapHandleRef.current?.panTo(target)
  }, [focusStop])

  return (
    <div ref={containerRef} className={className}>
      <TomTomMap ref={setHandle} className="h-full w-full" />
      <RefinedRouteLayer
        mapInstance={mapInstance}
        coordinates={coordinates ?? null}
      />
      <TripStopsLayer mapInstance={mapInstance} stops={trip.stops ?? []} />
      <button
        type="button"
        onClick={toggleFullscreen}
        aria-label={isFullscreen ? "Exit full screen" : "Enter full screen"}
        title={isFullscreen ? "Exit full screen" : "Enter full screen"}
        className="absolute bottom-4 right-4 z-10 flex h-8 w-8 items-center justify-center rounded-md border border-border/70 bg-white text-muted-foreground shadow-md hover:bg-muted dark:bg-slate-950"
      >
        {isFullscreen ? (
          <Minimize className="h-4 w-4" />
        ) : (
          <Maximize className="h-4 w-4" />
        )}
      </button>
    </div>
  )
}
