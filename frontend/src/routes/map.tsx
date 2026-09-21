import { useMutation } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useRef, useState } from "react"
import { getRouteOverview, searchAddress } from "@/api/map"
import type {
  FuelStationData,
  GeocodingSearchResponse,
  LayerError,
  TrafficLayerData,
  TruckRestrictionData,
} from "@/client"
import type { RestAreaFeatureCollection } from "@/client/types.gen"
import {
  FuelLayer,
  RestAreaLayer,
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
import {
  type AddressSelection,
  buildMapPointFromAddress,
  buildRouteOverviewRequest,
  createAddressSelection,
} from "@/lib/mapRequest"
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
  const [pickupAddress, setPickupAddress] = useState(
    "1521 Hickory Trail Allen TX 75002",
  )
  const [deliveryAddress, setDeliveryAddress] = useState(
    "3660 Gateway Street Springfield OR 97477",
  )
  const [pickupSuggestion, setPickupSuggestion] =
    useState<GeocodingSearchResponse | null>(null)
  const [deliverySuggestion, setDeliverySuggestion] =
    useState<GeocodingSearchResponse | null>(null)
  const [pickupSelection, setPickupSelection] =
    useState<AddressSelection | null>(null)
  const [deliverySelection, setDeliverySelection] =
    useState<AddressSelection | null>(null)
  const [isPickupSearching, setIsPickupSearching] = useState(false)
  const [isDeliverySearching, setIsDeliverySearching] = useState(false)

  // Layer state - each layer is stored and rendered independently
  const [routeCoordinates, setRouteCoordinates] = useState<Coordinate[] | null>(
    null,
  )
  const [traffic, setTraffic] = useState<TrafficLayerData | null>(null)
  const [fuelStations, setFuelStations] = useState<Array<FuelStationData>>([])
  const [truckRestrictions, setTruckRestrictions] = useState<
    Array<TruckRestrictionData>
  >([])
  const [restAreas, setRestAreas] = useState<RestAreaFeatureCollection | null>(
    null,
  )
  const [layerErrors, setLayerErrors] = useState<Array<LayerError>>([])
  const [routeInfo, setRouteInfo] = useState<RouteInfo | null>(null)

  const resetLayers = () => {
    setRouteCoordinates(null)
    setTraffic(null)
    setFuelStations([])
    setTruckRestrictions([])
    setRestAreas(null)
    setRouteInfo(null)
  }

  useEffect(() => {
    let cancelled = false
    const query = pickupAddress.trim()
    const selectedAddress = pickupSelection?.formatted_address

    if (query.length < 3 || query === selectedAddress) {
      setPickupSuggestion(null)
      setIsPickupSearching(false)
      return
    }

    setIsPickupSearching(true)
    const timer = window.setTimeout(async () => {
      try {
        const result = await searchAddress(query)
        if (!cancelled) {
          setPickupSuggestion(result)
        }
      } catch {
        if (!cancelled) {
          setPickupSuggestion(null)
        }
      } finally {
        if (!cancelled) {
          setIsPickupSearching(false)
        }
      }
    }, 300)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [pickupAddress, pickupSelection])

  useEffect(() => {
    let cancelled = false
    const query = deliveryAddress.trim()
    const selectedAddress = deliverySelection?.formatted_address

    if (query.length < 3 || query === selectedAddress) {
      setDeliverySuggestion(null)
      setIsDeliverySearching(false)
      return
    }

    setIsDeliverySearching(true)
    const timer = window.setTimeout(async () => {
      try {
        const result = await searchAddress(query)
        if (!cancelled) {
          setDeliverySuggestion(result)
        }
      } catch {
        if (!cancelled) {
          setDeliverySuggestion(null)
        }
      } finally {
        if (!cancelled) {
          setIsDeliverySearching(false)
        }
      }
    }, 300)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [deliveryAddress, deliverySelection])

  const mutation = useMutation({
    mutationFn: async (forceRefresh: boolean) => {
      const request = buildRouteOverviewRequest({
        pickup: buildMapPointFromAddress(
          pickupSelection?.formatted_address ?? pickupAddress.trim(),
        ),
        delivery: buildMapPointFromAddress(
          deliverySelection?.formatted_address ?? deliveryAddress.trim(),
        ),
      })

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
      setRestAreas(data.rest_areas ?? null)

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

  const canSubmit =
    pickupAddress.trim().length > 0 && deliveryAddress.trim().length > 0

  const applySuggestion = (
    field: "pickup" | "delivery",
    suggestion: GeocodingSearchResponse,
  ) => {
    if (field === "pickup") {
      setPickupSelection(
        createAddressSelection(pickupAddress.trim(), suggestion),
      )
      setPickupAddress(suggestion.formatted_address)
      setPickupSuggestion(null)
      return
    }

    setDeliverySelection(
      createAddressSelection(deliveryAddress.trim(), suggestion),
    )
    setDeliveryAddress(suggestion.formatted_address)
    setDeliverySuggestion(null)
  }

  const mapInstance = mapRef.current?.getMapInstance() || null

  return (
    <div className="p-4 h-screen flex flex-col gap-4">
      <div className="flex gap-4 flex-wrap">
        <Card className="flex-1 min-w-[300px]">
          <CardHeader className="pb-3">
            <CardTitle>Route Calculator</CardTitle>
            <CardDescription>
              Enter pickup and delivery addresses
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="pickup-address" className="text-sm font-medium">
                Pickup address
              </label>
              <Input
                id="pickup-address"
                placeholder="1521 Hickory Trail Allen TX 75002"
                value={pickupAddress}
                onChange={(e) => {
                  setPickupAddress(e.target.value)
                  if (e.target.value !== pickupSelection?.formatted_address) {
                    setPickupSelection(null)
                  }
                }}
              />
              {isPickupSearching && (
                <p className="text-xs text-gray-500">Searching address…</p>
              )}
              {pickupSuggestion &&
                pickupSuggestion.formatted_address !==
                  pickupSelection?.formatted_address && (
                  <button
                    type="button"
                    className="w-full rounded-md border px-3 py-2 text-left text-sm hover:bg-muted"
                    onClick={() => applySuggestion("pickup", pickupSuggestion)}
                  >
                    {pickupSuggestion.formatted_address}
                  </button>
                )}
            </div>

            <div className="space-y-2">
              <label htmlFor="delivery-address" className="text-sm font-medium">
                Delivery address
              </label>
              <Input
                id="delivery-address"
                placeholder="3660 Gateway Street Springfield OR 97477"
                value={deliveryAddress}
                onChange={(e) => {
                  setDeliveryAddress(e.target.value)
                  if (e.target.value !== deliverySelection?.formatted_address) {
                    setDeliverySelection(null)
                  }
                }}
              />
              {isDeliverySearching && (
                <p className="text-xs text-gray-500">Searching address…</p>
              )}
              {deliverySuggestion &&
                deliverySuggestion.formatted_address !==
                  deliverySelection?.formatted_address && (
                  <button
                    type="button"
                    className="w-full rounded-md border px-3 py-2 text-left text-sm hover:bg-muted"
                    onClick={() =>
                      applySuggestion("delivery", deliverySuggestion)
                    }
                  >
                    {deliverySuggestion.formatted_address}
                  </button>
                )}
            </div>

            <div className="flex gap-2">
              <Button
                onClick={handleCalculateRoute}
                disabled={mutation.isPending || !canSubmit}
                className="flex-1"
              >
                {mutation.isPending ? "Calculating..." : "Calculate Route"}
              </Button>
              <Button
                onClick={handleForceRefresh}
                disabled={mutation.isPending || !canSubmit}
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
                Error calculating route. Try different addresses.
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
            <p>
              <span className="font-medium">Rest areas:</span>{" "}
              {restAreas?.features?.length ?? 0}
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
        <RestAreaLayer mapInstance={mapInstance} restAreas={restAreas} />
      </div>
    </div>
  )
}
