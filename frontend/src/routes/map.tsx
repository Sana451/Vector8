import { createFileRoute } from "@tanstack/react-router"
import TomTomMap from "@/components/Map/TomTomMap"

export const Route = createFileRoute("/map")({
  component: MapPage,
})

function MapPage() {
  return (
    <div className="p-4">
      <h1 className="text-2xl mb-4">TomTom Map Test</h1>
      <TomTomMap />
    </div>
  )
}
