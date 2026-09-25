import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useRef, useState } from "react"
import { calculateFuelOptimization } from "@/api/fuelOptimization"
import { getRouteOverview, searchAddress } from "@/api/map"
import { listVehicles } from "@/api/vehicles"
import type {
  FuelStationData,
  GeocodingSearchResponse,
  TrafficLayerData,
  TruckRestrictionData,
  VehiclePublic,
} from "@/client"
import type { RestAreaFeatureCollection } from "@/client/types.gen"
import {
  LayerTogglePanel,
  type LayerType,
} from "@/components/Map/LayerTogglePanel"
import {
  FuelLayer,
  RestAreaLayer,
  RouteLayer,
  TrafficLayer,
  TruckRestrictionLayer,
} from "@/components/Map/layers"
import TomTomMap, { type TomTomMapHandle } from "@/components/Map/TomTomMap"
import { Button } from "@/components/ui/button"
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

export const Route = createFileRoute("/_layout/map")({
  component: MapPage,
})

interface RouteInfo {
  distance: string
  duration: string
}

function MapPage() {
  const mapRef = useRef<TomTomMapHandle>(null)
  const { showSuccessToast, showErrorToast } = useCustomToast()

  // Layer visibility state
  const [visibleLayers, setVisibleLayers] = useState<Set<LayerType>>(
    new Set(["route", "traffic", "fuel", "truck-restrictions", "rest-areas"]),
  )

  const handleToggleLayer = (layer: LayerType) => {
    setVisibleLayers((prev) => {
      const next = new Set(prev)
      if (next.has(layer)) {
        next.delete(layer)
        console.info(
          `[Map] Layer hidden: ${layer}`,
          `Visible layers: ${Array.from(next).join(", ")}`,
        )
      } else {
        next.add(layer)
        console.info(
          `[Map] Layer shown: ${layer}`,
          `Visible layers: ${Array.from(next).join(", ")}`,
        )
      }
      return next
    })
  }

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
  const [routeInfo, setRouteInfo] = useState<RouteInfo | null>(null)
  const [routeId, setRouteId] = useState<string | null>(null)
  const [selectedVehicleId, setSelectedVehicleId] = useState("")
  const [maxDetourMeters, setMaxDetourMeters] = useState("100000")
  const [initialFuelGallons, setInitialFuelGallons] = useState("42")
  const [reserveGallons, setReserveGallons] = useState("3")

  // Fetch vehicles list
  const { data: vehicles = [] } = useQuery<VehiclePublic[]>({
    queryKey: ["vehicles"],
    queryFn: listVehicles,
  })

  const resetLayers = () => {
    setRouteCoordinates(null)
    setTraffic(null)
    setFuelStations([])
    setTruckRestrictions([])
    setRestAreas(null)
    setRouteInfo(null)
    setRouteId(null)
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

      // Log all layer data for debugging
      console.group("[Map Layers] Route Overview Loaded")
      console.info("Route coordinates:", coordinates.length, "points")
      console.info("Traffic incidents:", data.traffic?.incidents?.length ?? 0)
      console.table(
        (data.traffic?.incidents ?? []).slice(0, 5).map((i: any) => ({
          severity: i.severity,
          type: i.type,
          count: i.estimated_percent_congestion,
        })),
      )
      console.info("Fuel stations:", data.fuel_stations?.length ?? 0)
      console.info("Truck restrictions:", data.truck_restrictions?.length ?? 0)
      console.table(
        (data.truck_restrictions ?? []).slice(0, 5).map((r: any) => ({
          type: r.type,
          severity: r.severity,
        })),
      )
      console.info(
        "Rest areas:",
        data.rest_areas?.features?.length ?? 0,
        "locations",
      )
      const restAreaCategories = new Set()
      data.rest_areas?.features?.forEach((f: any) => {
        restAreaCategories.add(f.properties?.primaryCategoryId)
      })
      console.info(
        "Rest area categories:",
        Array.from(restAreaCategories).join(", "),
      )
      console.groupEnd()

      const summary = data.route?.routes?.[0]?.summary
      if (summary) {
        const distanceKm = (summary.lengthInMeters / 1000).toFixed(1)
        const durationMin = Math.round(summary.travelDurationInSeconds / 60)
        setRouteInfo({
          distance: `${distanceKm} km`,
          duration: `${durationMin} min`,
        })
      }

      // Save route ID for fuel optimization (from API response)
      if (data.route?.id) {
        setRouteId(data.route.id)
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

  const fuelOptimizationMutation = useMutation({
    mutationFn: async () => {
      if (!routeId || !selectedVehicleId) {
        throw new Error("Route ID and vehicle ID are required")
      }

      return await calculateFuelOptimization({
        route_id: routeId,
        vehicle_id: selectedVehicleId,
        algorithm: "greedy",
        initial_fuel_gallons: parseInt(initialFuelGallons, 10),
        constraints: {
          reserve_gallons: parseInt(reserveGallons, 10),
          max_allowed_detour_meters: parseInt(maxDetourMeters, 10),
        },
        include_debug: false,
      })
    },
    onSuccess: (data) => {
      showSuccessToast("Fuel optimization calculated successfully")
      console.log("Fuel optimization result:", data)
    },
    onError: handleError.bind(showErrorToast),
  })

  const handleOptimizeFuel = () => {
    if (!selectedVehicleId) {
      showErrorToast("Please select a vehicle")
      return
    }
    fuelOptimizationMutation.mutate()
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
    <div className="flex flex-col w-full gap-2 h-[calc(100vh-100px)] overflow-hidden">
      {/* Route Calculator - горизонтальная панель сверху */}
      <div className="flex-shrink-0 border-b border-border/50 bg-background p-2">
        <div className="flex flex-wrap gap-2 items-end">
          {/* Pickup Address */}
          <div className="flex-1 min-w-[220px]">
            <label htmlFor="pickup-address" className="text-xs font-medium">
              Pickup
            </label>
            <div className="relative">
              <Input
                id="pickup-address"
                placeholder="1521 Hickory Trail..."
                value={pickupAddress}
                onChange={(e) => {
                  setPickupAddress(e.target.value)
                  if (e.target.value !== pickupSelection?.formatted_address) {
                    setPickupSelection(null)
                  }
                }}
                className="text-xs h-8"
              />
              {isPickupSearching && (
                <p className="text-xs text-muted-foreground absolute top-8 left-0 z-10">
                  Searching…
                </p>
              )}
              {pickupSuggestion &&
                pickupSuggestion.formatted_address !==
                  pickupSelection?.formatted_address && (
                  <button
                    type="button"
                    className="absolute top-8 left-0 w-full rounded-md border px-2 py-1 text-xs hover:bg-muted bg-white dark:bg-slate-950 z-10"
                    onClick={() => applySuggestion("pickup", pickupSuggestion)}
                  >
                    {pickupSuggestion.formatted_address}
                  </button>
                )}
            </div>
          </div>

          {/* Delivery Address */}
          <div className="flex-1 min-w-[220px]">
            <label htmlFor="delivery-address" className="text-xs font-medium">
              Delivery
            </label>
            <div className="relative">
              <Input
                id="delivery-address"
                placeholder="3660 Gateway Street..."
                value={deliveryAddress}
                onChange={(e) => {
                  setDeliveryAddress(e.target.value)
                  if (e.target.value !== deliverySelection?.formatted_address) {
                    setDeliverySelection(null)
                  }
                }}
                className="text-xs h-8"
              />
              {isDeliverySearching && (
                <p className="text-xs text-muted-foreground absolute top-8 left-0 z-10">
                  Searching…
                </p>
              )}
              {deliverySuggestion &&
                deliverySuggestion.formatted_address !==
                  deliverySelection?.formatted_address && (
                  <button
                    type="button"
                    className="absolute top-8 left-0 w-full rounded-md border px-2 py-1 text-xs hover:bg-muted bg-white dark:bg-slate-950 z-10"
                    onClick={() =>
                      applySuggestion("delivery", deliverySuggestion)
                    }
                  >
                    {deliverySuggestion.formatted_address}
                  </button>
                )}
            </div>
          </div>

          {/* Buttons */}
          <div className="flex gap-2 flex-wrap">
            <Button
              onClick={handleCalculateRoute}
              disabled={mutation.isPending || !canSubmit}
              className="text-xs h-8 px-3"
              size="sm"
            >
              {mutation.isPending ? "Calculating…" : "Calculate"}
            </Button>
            <Button
              onClick={handleForceRefresh}
              disabled={mutation.isPending || !canSubmit}
              variant="outline"
              className="text-xs h-8 px-3"
              size="sm"
            >
              Refresh
            </Button>
          </div>

          {/* Route Info */}
          {routeInfo && (
            <div className="flex gap-3 text-xs items-center flex-wrap">
              <div>
                <span className="font-medium">Distance:</span>{" "}
                {routeInfo.distance}
              </div>
              <div>
                <span className="font-medium">Duration:</span>{" "}
                {routeInfo.duration}
              </div>
            </div>
          )}

          {/* Error Message */}
          {mutation.isError && (
            <div className="text-xs text-red-600 dark:text-red-400 flex-wrap">
              Error calculating route
            </div>
          )}
        </div>
      </div>

      {/* Fuel Optimization Panel - показывается после расчета маршрута */}
      {routeId && (
        <div className="flex-shrink-0 border-b border-border/50 bg-background p-2">
          <div className="flex flex-wrap gap-2 items-end">
            <div className="flex-1 min-w-[200px]">
              <label htmlFor="vehicle-select" className="text-xs font-medium">
                Vehicle
              </label>
              <select
                id="vehicle-select"
                value={selectedVehicleId}
                onChange={(e) => setSelectedVehicleId(e.target.value)}
                className="w-full text-xs h-8 px-2 rounded border border-border bg-background"
              >
                <option value="">Select a vehicle...</option>
                {vehicles.map((vehicle) => (
                  <option key={vehicle.id} value={vehicle.id}>
                    {vehicle.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex-1 min-w-[150px]">
              <label htmlFor="initial-fuel" className="text-xs font-medium">
                Initial Fuel (gal)
              </label>
              <Input
                id="initial-fuel"
                type="number"
                value={initialFuelGallons}
                onChange={(e) => setInitialFuelGallons(e.target.value)}
                className="text-xs h-8"
                placeholder="42"
              />
            </div>

            <div className="flex-1 min-w-[150px]">
              <label htmlFor="reserve-fuel" className="text-xs font-medium">
                Reserve Fuel (gal)
              </label>
              <Input
                id="reserve-fuel"
                type="number"
                value={reserveGallons}
                onChange={(e) => setReserveGallons(e.target.value)}
                className="text-xs h-8"
                placeholder="3"
              />
            </div>

            <div className="flex-1 min-w-[160px]">
              <label htmlFor="max-detour" className="text-xs font-medium">
                Max Detour (m)
              </label>
              <Input
                id="max-detour"
                type="number"
                value={maxDetourMeters}
                onChange={(e) => setMaxDetourMeters(e.target.value)}
                className="text-xs h-8"
                placeholder="100000"
              />
            </div>

            <div className="flex gap-2">
              <Button
                onClick={handleOptimizeFuel}
                disabled={
                  fuelOptimizationMutation.isPending || !selectedVehicleId
                }
                className="text-xs h-8 px-3"
                size="sm"
              >
                {fuelOptimizationMutation.isPending
                  ? "Optimizing…"
                  : "Optimize Fuel"}
              </Button>
            </div>

            {fuelOptimizationMutation.isError && (
              <div className="text-xs text-red-600 dark:text-red-400 flex-wrap">
                Optimization error
              </div>
            )}
          </div>
        </div>
      )}
      <div className="flex-1 min-h-0 relative w-full overflow-hidden">
        <TomTomMap ref={mapRef} />
        <LayerTogglePanel
          visibleLayers={visibleLayers}
          onToggleLayer={handleToggleLayer}
          counts={{
            traffic: traffic?.incidents?.length ?? 0,
            fuel: fuelStations.length,
            "truck-restrictions": truckRestrictions.length,
            "rest-areas": restAreas?.features?.length ?? 0,
          }}
        />
        {visibleLayers.has("route") && (
          <RouteLayer
            mapInstance={mapInstance}
            coordinates={routeCoordinates}
          />
        )}
        {visibleLayers.has("traffic") && (
          <TrafficLayer mapInstance={mapInstance} traffic={traffic} />
        )}
        {visibleLayers.has("fuel") && (
          <FuelLayer mapInstance={mapInstance} stations={fuelStations} />
        )}
        {visibleLayers.has("truck-restrictions") && (
          <TruckRestrictionLayer
            mapInstance={mapInstance}
            restrictions={truckRestrictions}
          />
        )}
        {visibleLayers.has("rest-areas") && (
          <RestAreaLayer mapInstance={mapInstance} restAreas={restAreas} />
        )}
      </div>
    </div>
  )
}
