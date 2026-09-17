import { TomTomMap as TTMap } from "@tomtom-org/maps-sdk/map"
import { useEffect, useRef } from "react"
import "./TomTomMap.css"

export default function TomTomMap() {
  const mapRef = useRef<HTMLDivElement | null>(null)

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

    map.mapLibreMap.on("load", () => {
      console.log("Map loaded")
    })

    map.mapLibreMap.on("error", (e) => {
      console.error("Map error", e)
    })

    return () => map.mapLibreMap.remove()
  }, [])

  return <div ref={mapRef} className="tomtom-map" />
}
