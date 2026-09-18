import { TomTomMap as TTMap } from "@tomtom-org/maps-sdk/map"
import type { Map as MapLibreMap } from "maplibre-gl"
import { forwardRef, useEffect, useRef } from "react"
import "./TomTomMap.css"

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
const TomTomMap = forwardRef<TomTomMapHandle>((_props, ref) => {
  const mapRef = useRef<HTMLDivElement | null>(null)
  const mapInstanceRef = useRef<MapLibreMap | null>(null)

  useEffect(() => {
    if (!mapRef.current) return

    const map = new TTMap({
      style: "standardLight",
      mapLibre: {
        container: mapRef.current,
        center: [4.8156, 52.4414],
        zoom: 8,
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

  return <div ref={mapRef} className="tomtom-map" />
})

TomTomMap.displayName = "TomTomMap"

export default TomTomMap
