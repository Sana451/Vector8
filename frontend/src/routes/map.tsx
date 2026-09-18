import { useMutation } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useRef, useState } from "react"
import { calculateRoute } from "@/api/routing"
import { RouteLayer } from "@/components/Map/RouteLayer"
import TomTomMap, { type TomTomMapHandle } from "@/components/Map/TomTomMap"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import useCustomToast from "@/hooks/useCustomToast"
import {
  type Coordinate,
  calculateBoundingBox,
  extractRouteCoordinates,
} from "@/lib/routing"
import { handleError } from "@/utils"

export const Route = createFileRoute("/map")({
  component: MapPage,
})

function MapPage() {
  const mapRef = useRef<TomTomMapHandle>(null)
  const { showSuccessToast, showErrorToast } = useCustomToast()

  // Form state
  const [originLon, setOriginLon] = useState("-74.006")
  const [originLat, setOriginLat] = useState("40.7128")
  const [destLon, setDestLon] = useState("-73.9855")
  const [destLat, setDestLat] = useState("40.758")

  // Route state
  const [routeCoordinates, setRouteCoordinates] = useState<Coordinate[] | null>(
    null,
  )
  const [routeInfo, setRouteInfo] = useState<{
    distance: string
    duration: string
  } | null>(null)

  const mutation = useMutation({
    mutationFn: async (forceRefresh: boolean) => {
      const request = {
        route_planning_locations: {
          origin: {
            type: "Point" as const,
            coordinates: [parseFloat(originLon), parseFloat(originLat)] as [
              number,
              number,
            ],
          },
          destination: {
            type: "Point" as const,
            coordinates: [parseFloat(destLon), parseFloat(destLat)] as [
              number,
              number,
            ],
          },
        },
      }

      return await calculateRoute(request, forceRefresh)
    },
    onSuccess: (data) => {
      const coordinates = extractRouteCoordinates(data)
      if (!coordinates || coordinates.length < 2) {
        setRouteCoordinates(null)
        setRouteInfo(null)
        showErrorToast("Route could not be calculated or has invalid geometry")
        return
      }

      setRouteCoordinates(coordinates)

      // Extract summary info from first route
      if (data.routes && data.routes.length > 0) {
        const summary = data.routes[0].summary
        const distanceKm = (summary.lengthInMeters / 1000).toFixed(1)
        const durationMin = Math.round(summary.travelDurationInSeconds / 60)
        setRouteInfo({
          distance: `${distanceKm} km`,
          duration: `${durationMin} min`,
        })
      }

      // Fit map bounds to route
      const bbox = calculateBoundingBox(coordinates)
      mapRef.current?.fitBounds(bbox)

      showSuccessToast("Route calculated successfully")
    },
    onError: handleError.bind(showErrorToast),
  })

  const handleCalculateRoute = () => {
    mutation.mutate(false)
  }

  const handleForceRefresh = () => {
    mutation.mutate(true)
  }

  const mapInstance = mapRef.current?.getMapInstance() || null

  return (
    <div className="p-4 h-screen flex flex-col gap-4">
      <div className="flex gap-4 flex-wrap">
        <Card className="flex-1 min-w-[300px]">
          <CardHeader className="pb-3">
            <CardTitle>Route Calculator</CardTitle>
            <CardDescription>
              Enter origin and destination coordinates
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="origin-lon" className="text-sm font-medium">
                Origin
              </label>
              <div className="flex gap-2">
                <Input
                  id="origin-lon"
                  type="number"
                  placeholder="Longitude"
                  value={originLon}
                  onChange={(e) => setOriginLon(e.target.value)}
                  step="0.0001"
                />
                <Input
                  type="number"
                  placeholder="Latitude"
                  value={originLat}
                  onChange={(e) => setOriginLat(e.target.value)}
                  step="0.0001"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="dest-lon" className="text-sm font-medium">
                Destination
              </label>
              <div className="flex gap-2">
                <Input
                  id="dest-lon"
                  type="number"
                  placeholder="Longitude"
                  value={destLon}
                  onChange={(e) => setDestLon(e.target.value)}
                  step="0.0001"
                />
                <Input
                  type="number"
                  placeholder="Latitude"
                  value={destLat}
                  onChange={(e) => setDestLat(e.target.value)}
                  step="0.0001"
                />
              </div>
            </div>

            <div className="flex gap-2">
              <Button
                onClick={handleCalculateRoute}
                disabled={mutation.isPending}
                className="flex-1"
              >
                {mutation.isPending ? "Calculating..." : "Calculate Route"}
              </Button>
              <Button
                onClick={handleForceRefresh}
                disabled={mutation.isPending}
                variant="outline"
                className="flex-1"
              >
                Refresh
              </Button>
            </div>

            {routeInfo && (
              <div className="mt-4 p-3 bg-blue-50 rounded text-sm">
                <p className="text-gray-700">
                  <span className="font-medium">Distance:</span>{" "}
                  {routeInfo.distance}
                </p>
                <p className="text-gray-700">
                  <span className="font-medium">Duration:</span>{" "}
                  {routeInfo.duration}
                </p>
              </div>
            )}

            {mutation.isError && (
              <div className="mt-4 p-3 bg-red-50 rounded text-sm text-red-700">
                Error calculating route. Try different coordinates.
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="flex-1 min-w-[300px]">
          <CardHeader className="pb-3">
            <CardTitle>Instructions</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-gray-600 space-y-2">
            <p>
              1. Enter origin longitude and latitude (format: decimal degrees)
            </p>
            <p>2. Enter destination longitude and latitude</p>
            <p>3. Click "Calculate Route" to compute the route</p>
            <p>4. The route will be displayed on the map as a blue line</p>
            <p>5. Use "Refresh" to bypass cache and recalculate</p>
            <p className="text-xs text-gray-500 mt-4">
              Example: New York to Times Square
              <br />
              Origin: [-74.006, 40.7128]
              <br />
              Destination: [-73.9855, 40.758]
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="flex-1 min-h-0">
        <TomTomMap ref={mapRef} />
        <RouteLayer mapInstance={mapInstance} coordinates={routeCoordinates} />
      </div>
    </div>
  )
}
