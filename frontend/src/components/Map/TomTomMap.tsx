import { TomTomMap as TTMap } from "@tomtom-org/maps-sdk/map"
import type { Map as MapLibreMap } from "maplibre-gl"
import { forwardRef, useEffect, useRef } from "react"
import "./TomTomMap.css"

const DEFAULT_US_MAP_CENTER: [number, number] = [-98.5795, 39.8283]
const DEFAULT_US_MAP_ZOOM = 3.5

export interface TomTomMapHandle {
  getMapInstance: () => MapLibreMap | null
  fitBounds: (bbox: [number, number, number, number], padding?: number) => void
}

/**
 * TomTomMap component
 *
 * Renders TomTom map using MapLibre SDK.
 * Exposes map instance and utility methods through ref.
 */
const TomTomMap = forwardRef<TomTomMapHandle>(
  ({ className }: { className?: string }, ref) => {
    const mapRef = useRef<HTMLDivElement | null>(null)
    const mapInstanceRef = useRef<MapLibreMap | null>(null)

    useEffect(() => {
      if (!mapRef.current) return

      const map = new TTMap({
        style: "standardLight",
        mapLibre: {
          container: mapRef.current,
          center: DEFAULT_US_MAP_CENTER,
          zoom: DEFAULT_US_MAP_ZOOM,
        },
      })

      mapInstanceRef.current = map.mapLibreMap

      map.mapLibreMap.on("load", () => {
        console.log("Map loaded")
      })

      map.mapLibreMap.on("error", (e) => {
        console.error("Map error", e)
      })

      return () => {
        mapInstanceRef.current = null
        map.mapLibreMap.remove()
      }
    }, [])

    // Expose map instance and methods through ref
    useEffect(() => {
      if (typeof ref === "function") {
        ref({
          getMapInstance: () => mapInstanceRef.current,
          fitBounds: (bbox: [number, number, number, number], padding = 50) => {
            mapInstanceRef.current?.fitBounds(bbox, { padding })
          },
        })
      } else if (ref) {
        ref.current = {
          getMapInstance: () => mapInstanceRef.current,
          fitBounds: (bbox: [number, number, number, number], padding = 50) => {
            mapInstanceRef.current?.fitBounds(bbox, { padding })
          },
        }
      }
    }, [ref])

    return <div ref={mapRef} className={`tomtom-map ${className || ""}`} />
  },
)

TomTomMap.displayName = "TomTomMap"

export default TomTomMap
