import { useMutation } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useRef, useState } from "react"
import { getRouteOverview } from "@/api/map"
import type {
  FuelStationData,
  LayerError,
  TrafficLayerData,
  TruckRestrictionData,
} from "@/client"
import {
  FuelLayer,
  RouteLayer,
  TrafficLayer,
  TruckRestrictionLayer,
} from "@/components/Map/layers"
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
import { extractOverviewCoordinates } from "@/lib/mapLayers"
import { type Coordinate, calculateBoundingBox } from "@/lib/routing"
import { handleError } from "@/utils"

export const Route = createFileRoute("/map")({
  component: MapPage,
})

interface RouteInfo {
  distance: string
  duration: string
}

function MapPage() {
  const mapRef = useRef<TomTomMapHandle>(null)
  const { showSuccessToast, showErrorToast } = useCustomToast()

  // Form state
  const [originLon, setOriginLon] = useState("-74.006")
  const [originLat, setOriginLat] = useState("40.7128")
  const [destLon, setDestLon] = useState("-73.9855")
  const [destLat, setDestLat] = useState("40.758")

  // Layer state - each layer is stored and rendered independently
  const [routeCoordinates, setRouteCoordinates] = useState<Coordinate[] | null>(
    null,
  )
  const [traffic, setTraffic] = useState<TrafficLayerData | null>(null)
  const [fuelStations, setFuelStations] = useState<Array<FuelStationData>>([])
  const [truckRestrictions, setTruckRestrictions] = useState<
    Array<TruckRestrictionData>
  >([])
  const [layerErrors, setLayerErrors] = useState<Array<LayerError>>([])
  const [routeInfo, setRouteInfo] = useState<RouteInfo | null>(null)

  const resetLayers = () => {
    setRouteCoordinates(null)
    setTraffic(null)
    setFuelStations([])
    setTruckRestrictions([])
    setRouteInfo(null)
  }

  const mutation = useMutation({
    mutationFn: async (forceRefresh: boolean) => {
      const request = {
        route: {
          route_planning_locations: {
            origin: {
              type: "Point" as const,
              coordinates: [
                Number.parseFloat(originLon),
                Number.parseFloat(originLat),
              ] as [number, number],
            },
            destination: {
              type: "Point" as const,
              coordinates: [
                Number.parseFloat(destLon),
                Number.parseFloat(destLat),
              ] as [number, number],
            },
          },
        },
      }

      return await getRouteOverview(request, forceRefresh)
    },
    onSuccess: (data) => {
      setLayerErrors(data.errors ?? [])

      const coordinates = extractOverviewCoordinates(data)
      if (!coordinates) {
        resetLayers()
        showErrorToast("Route could not be calculated or has invalid geometry")
        return
      }

      setRouteCoordinates(coordinates)
      setTraffic(data.traffic ?? null)
      setFuelStations(data.fuel_stations ?? [])
      setTruckRestrictions(data.truck_restrictions ?? [])

      const summary = data.route?.routes?.[0]?.summary
      if (summary) {
        const distanceKm = (summary.lengthInMeters / 1000).toFixed(1)
        const durationMin = Math.round(summary.travelDurationInSeconds / 60)
        setRouteInfo({
          distance: `${distanceKm} km`,
          duration: `${durationMin} min`,
        })
      }

      mapRef.current?.fitBounds(calculateBoundingBox(coordinates))

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
            <CardTitle>Layers</CardTitle>
            <CardDescription>
              Each layer is resolved independently by its provider
            </CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-gray-600 space-y-2">
            <p>
              <span className="font-medium">Traffic:</span>{" "}
              {traffic ? `${traffic.incidents?.length ?? 0} incidents` : "—"}
            </p>
            <p>
              <span className="font-medium">Fuel stations:</span>{" "}
              {fuelStations.length}
            </p>
            <p>
              <span className="font-medium">Truck restrictions:</span>{" "}
              {truckRestrictions.length}
            </p>

            {layerErrors.length > 0 && (
              <div className="mt-4 p-3 bg-amber-50 rounded text-amber-800 space-y-1">
                <p className="font-medium">Some layers are unavailable:</p>
                {layerErrors.map((error) => (
                  <p
                    key={`${error.layer}-${error.message}`}
                    className="text-xs"
                  >
                    {error.layer}
                    {error.provider ? ` (${error.provider})` : ""}:{" "}
                    {error.message}
                  </p>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="flex-1 min-h-0">
        <TomTomMap ref={mapRef} />
        <RouteLayer mapInstance={mapInstance} coordinates={routeCoordinates} />
        <TrafficLayer mapInstance={mapInstance} traffic={traffic} />
        <FuelLayer mapInstance={mapInstance} stations={fuelStations} />
        <TruckRestrictionLayer
          mapInstance={mapInstance}
          restrictions={truckRestrictions}
        />
      </div>
    </div>
  )
}
