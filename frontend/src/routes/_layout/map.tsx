import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Maximize, Minimize } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { calculateFuelOptimization } from "@/api/fuelOptimization"
import { getAllFuelStations, getRouteOverview, searchAddress } from "@/api/map"
import { listVehicles } from "@/api/vehicles"
import type {
  FuelOptimizationCalculateResponse,
  FuelStationData,
  GeocodingSearchResponse,
  TrafficLayerData,
  TruckRestrictionData,
  VehicleConstraintsInfo,
  VehiclePublic,
} from "@/client"
import type { RestAreaFeatureCollection } from "@/client/types.gen"
import { FloatingPanel } from "@/components/Map/FloatingPanel"
import {
  LayerTogglePanel,
  type LayerType,
} from "@/components/Map/LayerTogglePanel"
import {
  DetourLayer,
  FuelLayer,
  OptimizationComparedStationsLayer,
  OptimizationRejectedStationsLayer,
  OptimizationStopsLayer,
  ReachableRouteLayer,
  RestAreaLayer,
  RouteLayer,
  TrafficLayer,
  TruckRestrictionLayer,
} from "@/components/Map/layers"
import { MeasureTool } from "@/components/Map/MeasureTool"
import { OptimizationWalkthrough } from "@/components/Map/OptimizationWalkthrough"
import TomTomMap, { type TomTomMapHandle } from "@/components/Map/TomTomMap"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { VehicleSelector } from "@/components/VehicleSelector"
import useCustomToast from "@/hooks/useCustomToast"
import {
  buildOptimizationSteps,
  calculateRouteTotalDistanceMeters,
  getDefaultReserveGallons,
  getReserveLimits,
} from "@/lib/fuelOptimizationWalkthrough"
import { extractOverviewCoordinates } from "@/lib/mapLayers"
import {
  type AddressSelection,
  buildMapPointFromAddress,
  buildRouteOverviewRequest,
  createAddressSelection,
} from "@/lib/mapRequest"
import { type Coordinate, calculateBoundingBox } from "@/lib/routing"
import {
  describeAppliedConstraints,
  formatRoutingSummary,
  getMissingRoutingFields,
  getVehicleConstraintsWarning,
} from "@/lib/vehicleRouting"
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
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)

  useEffect(() => {
    const onChange = () => {
      setIsFullscreen(document.fullscreenElement === mapContainerRef.current)
    }
    document.addEventListener("fullscreenchange", onChange)
    return () => {
      document.removeEventListener("fullscreenchange", onChange)
      if (document.fullscreenElement === mapContainerRef.current) {
        void document.exitFullscreen()
      }
    }
  }, [])

  const toggleFullscreen = () => {
    const container = mapContainerRef.current
    if (!container) return
    if (document.fullscreenElement === container) {
      void document.exitFullscreen()
      return
    }
    container.requestFullscreen().catch(() => {
      showErrorToast("Full screen mode is not available")
    })
  }
  const { showSuccessToast, showErrorToast } = useCustomToast()

  // Layer visibility state
  const [visibleLayers, setVisibleLayers] = useState<Set<LayerType>>(
    new Set([
      "route",
      "detour",
      "traffic",
      "fuel",
      "truck-restrictions",
      "rest-areas",
      "optimization-stops",
    ]),
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
  // Suggestions only appear after the user types, not for prefilled defaults.
  const [pickupEdited, setPickupEdited] = useState(false)
  const [deliveryEdited, setDeliveryEdited] = useState(false)
  const [isDeliverySearching, setIsDeliverySearching] = useState(false)

  // Layer state - each layer is stored and rendered independently
  const [routeCoordinates, setRouteCoordinates] = useState<Coordinate[] | null>(
    null,
  )
  const [traffic, setTraffic] = useState<TrafficLayerData | null>(null)
  const [fuelStations, setFuelStations] = useState<Array<FuelStationData>>([])
  const [activeFuelStationIds, setActiveFuelStationIds] = useState<Set<string>>(
    new Set(),
  )
  const [truckRestrictions, setTruckRestrictions] = useState<
    Array<TruckRestrictionData>
  >([])
  const [restAreas, setRestAreas] = useState<RestAreaFeatureCollection | null>(
    null,
  )
  const [routeInfo, setRouteInfo] = useState<RouteInfo | null>(null)
  const [routeId, setRouteId] = useState<string | null>(null)
  const [selectedVehicleId, setSelectedVehicleId] = useState("")
  const [useVehicleConstraints, setUseVehicleConstraints] = useState(true)
  // What the last calculated route was built with, to flag stale routes.
  const [calculatedWith, setCalculatedWith] = useState<{
    vehicleId: string
    enabled: boolean
  } | null>(null)
  const [appliedConstraints, setAppliedConstraints] =
    useState<VehicleConstraintsInfo | null>(null)
  const [maxDetourMeters, setMaxDetourMeters] = useState("5000")
  const [initialFuelGallons, setInitialFuelGallons] = useState("42")
  const [reserveGallons, setReserveGallons] = useState("3")
  const [minRefuelGallons, setMinRefuelGallons] = useState("")
  const [optimizationResult, setOptimizationResult] =
    useState<FuelOptimizationCalculateResponse | null>(null)
  const [optimizationReserveGallons, setOptimizationReserveGallons] =
    useState(0)
  const [activeStepIndex, setActiveStepIndex] = useState(0)
  const [comparisonOpen, setComparisonOpen] = useState(false)

  // Fetch vehicles list
  // Distinct key: the fleet page caches a {data, count} object under
  // ["vehicles"]; invalidating ["vehicles"] still refreshes this list too.
  const { data: vehicles = [] } = useQuery<VehiclePublic[]>({
    queryKey: ["vehicles", "list"],
    queryFn: listVehicles,
  })

  // Fetch all available fuel stations on component mount
  useEffect(() => {
    const loadFuelStations = async () => {
      try {
        const stations = await getAllFuelStations(3000)
        setFuelStations(stations)
        console.info("[Map] Loaded", stations.length, "fuel stations on mount")
      } catch (error) {
        console.error("[Map] Failed to load fuel stations:", error)
      }
    }
    loadFuelStations()
  }, [])

  const resetLayers = () => {
    setRouteCoordinates(null)
    setTraffic(null)
    // Do NOT reset fuel stations - they are loaded once on mount and persist
    setActiveFuelStationIds(new Set())
    setTruckRestrictions([])
    setRestAreas(null)
    setRouteInfo(null)
    setRouteId(null)
    setAppliedConstraints(null)
    setCalculatedWith(null)
    setOptimizationResult(null)
    setActiveStepIndex(0)
  }

  useEffect(() => {
    let cancelled = false
    const query = pickupAddress.trim()
    const selectedAddress = pickupSelection?.formatted_address

    if (!pickupEdited || query.length < 3 || query === selectedAddress) {
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
  }, [pickupAddress, pickupSelection, pickupEdited])

  useEffect(() => {
    let cancelled = false
    const query = deliveryAddress.trim()
    const selectedAddress = deliverySelection?.formatted_address

    if (!deliveryEdited || query.length < 3 || query === selectedAddress) {
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
  }, [deliveryAddress, deliverySelection, deliveryEdited])

  const mutation = useMutation({
    mutationFn: async (forceRefresh: boolean) => {
      const request = buildRouteOverviewRequest({
        pickup: buildMapPointFromAddress(
          pickupSelection?.formatted_address ?? pickupAddress.trim(),
        ),
        delivery: buildMapPointFromAddress(
          deliverySelection?.formatted_address ?? deliveryAddress.trim(),
        ),
        vehicleId: selectedVehicleId || undefined,
        applyVehicleConstraints: useVehicleConstraints,
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
      // Do NOT update fuel stations - they are loaded once on mount and persist
      setTruckRestrictions(data.truck_restrictions ?? [])
      setRestAreas(data.rest_areas ?? null)
      setAppliedConstraints(data.vehicle_constraints ?? null)
      setCalculatedWith({
        vehicleId: selectedVehicleId,
        enabled: useVehicleConstraints,
      })

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
        const distanceMi = (summary.lengthInMeters / 1609.344).toFixed(1)
        const durationMin = Math.round(summary.travelDurationInSeconds / 60)
        setRouteInfo({
          distance: `${distanceKm} km (${distanceMi} mi)`,
          duration: `${durationMin} min (${Math.floor(durationMin / 1440)} d ${Math.floor((durationMin % 1440) / 60)} h)`,
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
          reserve_gallons: parseFloat(reserveGallons),
          min_refuel_gallons: minRefuelGallons.trim()
            ? Number.parseFloat(minRefuelGallons)
            : null,
          max_allowed_detour_meters: parseInt(maxDetourMeters, 10),
        },
        include_debug: false,
      })
    },
    onSuccess: (data) => {
      // Always keep the full result so rejected stations can be highlighted
      // on the map, even when the optimization itself is infeasible.
      setOptimizationResult(data)
      setOptimizationReserveGallons(parseFloat(reserveGallons) || 0)
      setActiveStepIndex(0)
      setActiveFuelStationIds(
        new Set((data.stops ?? []).map((stop) => stop.station_id)),
      )

      // Check optimization status
      if (data.status === "infeasible") {
        // Optimization is not possible
        const explanation = data.explanation

        // Build error message: "Optimization is infeasible." + outcome + all key_points
        let toastMessage = "Optimization is infeasible."

        if (explanation.outcome) {
          toastMessage += `\n${explanation.outcome}`
        }

        if (explanation.key_points && explanation.key_points.length > 0) {
          toastMessage += `\n\n${explanation.key_points.join("\n")}`
        }

        // Show error in toast
        showErrorToast(toastMessage)

        // Build detailed message for console with all details
        let consoleMessage = "Optimization is infeasible."

        if (explanation.outcome) {
          consoleMessage += `\n\nOutcome: ${explanation.outcome}`
        }

        if (explanation.key_points && explanation.key_points.length > 0) {
          consoleMessage += `\n\nKey Points:\n${explanation.key_points.join("\n")}`
        }

        // Add information about filtered out stations
        if (
          explanation.skipped_station_stats &&
          explanation.skipped_station_stats.length > 0
        ) {
          const stationStats = explanation.skipped_station_stats[0]
          if (stationStats.count > 0) {
            consoleMessage += `\n\n⚠️ ${stationStats.count} station(s) were excluded: ${stationStats.description}`
            if (
              stationStats.sample_points &&
              stationStats.sample_points.length > 0
            ) {
              consoleMessage +=
                "\n   Examples: " +
                stationStats.sample_points
                  .slice(0, 3)
                  .map((s) => s.name)
                  .join(", ")
            }
          }
        }

        // Log full details for debugging
        console.warn("[Fuel Optimization] Infeasible", consoleMessage, {
          summary: explanation.summary,
          outcome: explanation.outcome,
          warnings: explanation.warnings,
          allKeyPoints: explanation.key_points,
          skippedStations: explanation.skipped_station_stats,
        })

        return
      }

      // Optimization succeeded
      if (data.status === "success") {
        // Build success message with summary
        const summary = data.summary
        let successMessage = "Fuel optimization calculated successfully"
        if (summary) {
          successMessage += ` — ${summary.number_of_stops} stops, $${summary.total_fuel_cost} cost`
        }

        showSuccessToast(successMessage)
        console.log("Fuel optimization result:", data)
      }
    },
    onError: handleError.bind(showErrorToast),
  })

  const reserveLimits = useMemo(() => {
    const vehicle = vehicles.find((v) => v.id === selectedVehicleId)
    return getReserveLimits(Number(vehicle?.usable_tank_capacity_gallons))
  }, [vehicles, selectedVehicleId])

  const handleOptimizeFuel = () => {
    if (!selectedVehicleId) {
      showErrorToast("Please select a vehicle")
      return
    }
    const reserve = Number.parseFloat(reserveGallons)
    if (
      !Number.isFinite(reserve) ||
      (reserveLimits &&
        (reserve < reserveLimits.min || reserve > reserveLimits.max))
    ) {
      showErrorToast(
        reserveLimits
          ? `Reserve must be between ${reserveLimits.min} and ${reserveLimits.max} gal (25% of tank)`
          : "Enter a valid reserve",
      )
      return
    }
    fuelOptimizationMutation.mutate()
  }

  // Walkthrough steps: start -> each refuel stop (in order) -> destination.
  const optimizationSteps = useMemo(() => {
    if (!optimizationResult || !routeCoordinates) {
      return []
    }
    return buildOptimizationSteps({
      response: optimizationResult,
      routeCoordinates,
      fuelStations,
      initialFuelGallons: Number.parseFloat(initialFuelGallons) || 0,
    })
  }, [optimizationResult, routeCoordinates, fuelStations, initialFuelGallons])

  const routeTotalDistanceMeters = useMemo(
    () => calculateRouteTotalDistanceMeters(routeCoordinates),
    [routeCoordinates],
  )

  const activeOptimizationStep = optimizationSteps[activeStepIndex] ?? null

  const handleSelectVehicle = (vehicleId: string) => {
    setSelectedVehicleId(vehicleId)
    const vehicle = vehicles.find((v) => v.id === vehicleId)
    const reserve = getDefaultReserveGallons(
      Number(vehicle?.usable_tank_capacity_gallons),
    )
    if (reserve !== null) {
      setReserveGallons(String(reserve))
    }
  }

  const handleStepChange = (index: number) => {
    const clamped = Math.max(0, Math.min(index, optimizationSteps.length - 1))
    setActiveStepIndex(clamped)
    const step = optimizationSteps[clamped]
    if (step) {
      mapRef.current?.panTo(step.coordinate)
    }
  }

  const canSubmit =
    pickupAddress.trim().length > 0 && deliveryAddress.trim().length > 0

  const selectedVehicle = vehicles.find((v) => v.id === selectedVehicleId)
  const constraintsWarning = useMemo(() => {
    if (!useVehicleConstraints || !selectedVehicle) return null
    return getVehicleConstraintsWarning(
      getMissingRoutingFields(selectedVehicle),
    )
  }, [useVehicleConstraints, selectedVehicle])
  const appliedSummary = describeAppliedConstraints(appliedConstraints)
  const constraintsStale =
    calculatedWith !== null &&
    (calculatedWith.vehicleId !== selectedVehicleId ||
      calculatedWith.enabled !== useVehicleConstraints)

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
      <div
        ref={mapContainerRef}
        className="flex-1 min-h-0 relative w-full overflow-hidden"
      >
        <TomTomMap ref={mapRef} />
        <div className="pointer-events-none absolute left-2 top-2 flex max-w-[calc(100%-1rem)] flex-col gap-2">
          <FloatingPanel
            title="Route"
            boundsRef={mapContainerRef}
            collapsedSummary={
              routeInfo ? (
                <span className="text-xs text-muted-foreground">
                  {routeInfo.distance} · {routeInfo.duration}
                </span>
              ) : null
            }
          >
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
                      setPickupEdited(true)
                      setPickupAddress(e.target.value)
                      if (
                        e.target.value !== pickupSelection?.formatted_address
                      ) {
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
                        onClick={() =>
                          applySuggestion("pickup", pickupSuggestion)
                        }
                      >
                        {pickupSuggestion.formatted_address}
                      </button>
                    )}
                </div>
              </div>

              {/* Delivery Address */}
              <div className="flex-1 min-w-[220px]">
                <label
                  htmlFor="delivery-address"
                  className="text-xs font-medium"
                >
                  Delivery
                </label>
                <div className="relative">
                  <Input
                    id="delivery-address"
                    placeholder="3660 Gateway Street..."
                    value={deliveryAddress}
                    onChange={(e) => {
                      setDeliveryEdited(true)
                      setDeliveryAddress(e.target.value)
                      if (
                        e.target.value !== deliverySelection?.formatted_address
                      ) {
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

              {/* Vehicle & routing constraints */}
              <div className="flex w-full flex-wrap items-start gap-2">
                <VehicleSelector
                  vehicles={vehicles}
                  selectedVehicleId={selectedVehicleId}
                  onSelectVehicle={handleSelectVehicle}
                />
                <div className="min-w-[220px] flex-1 space-y-1">
                  <label
                    htmlFor="use-vehicle-constraints"
                    className="flex items-center gap-2 pt-4 text-xs font-medium"
                  >
                    <Checkbox
                      id="use-vehicle-constraints"
                      checked={useVehicleConstraints}
                      onCheckedChange={(checked) =>
                        setUseVehicleConstraints(checked === true)
                      }
                    />
                    Use vehicle dimensions &amp; weight in routing
                  </label>
                  {useVehicleConstraints && !selectedVehicle && (
                    <p className="text-xs text-muted-foreground">
                      Select a vehicle to apply its restrictions.
                    </p>
                  )}
                  {constraintsWarning && (
                    <p
                      role="alert"
                      className="rounded border border-amber-500/50 bg-amber-500/10 px-2 py-1 text-xs text-amber-700 dark:text-amber-400"
                    >
                      {constraintsWarning.allMissing
                        ? "This vehicle has no dimensions or weight set, so HERE will ignore all physical restrictions. "
                        : `Not set for this vehicle: ${constraintsWarning.missing.join(", ")}. HERE will ignore the matching restrictions. `}
                      <Link to="/fleet" className="underline">
                        Edit in Fleet
                      </Link>
                    </p>
                  )}
                  {selectedVehicle &&
                    useVehicleConstraints &&
                    !constraintsWarning &&
                    formatRoutingSummary(selectedVehicle) && (
                      <p className="text-xs text-muted-foreground">
                        {formatRoutingSummary(selectedVehicle)}
                      </p>
                    )}
                  {appliedSummary && !constraintsStale && (
                    <p className="text-xs text-muted-foreground">
                      Route built with {appliedSummary.sentCount} vehicle
                      parameter{appliedSummary.sentCount === 1 ? "" : "s"}.
                    </p>
                  )}
                  {constraintsStale && (
                    <p className="text-xs text-muted-foreground">
                      Vehicle settings changed. Recalculate the route to apply
                      them.
                    </p>
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
          </FloatingPanel>
          {/* Fuel Optimization Panel - показывается после расчета маршрута */}
          {routeId && (
            <FloatingPanel
              title="Fuel Optimization"
              boundsRef={mapContainerRef}
            >
              <div className="flex flex-wrap gap-2 items-end">
                <div className="flex-1 min-w-[200px]">
                  <span className="text-xs font-medium">Vehicle</span>
                  <div className="flex h-8 items-center text-xs">
                    {selectedVehicle
                      ? `${selectedVehicle.name} (${selectedVehicle.unit_number})`
                      : "Select a vehicle in the Route panel"}
                  </div>
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
                    min={reserveLimits?.min ?? 0}
                    max={reserveLimits?.max}
                    step="0.1"
                    value={reserveGallons}
                    onKeyDown={(e) => {
                      if (["-", "+", "e", "E"].includes(e.key))
                        e.preventDefault()
                    }}
                    onChange={(e) => {
                      if (!e.target.value.startsWith("-")) {
                        setReserveGallons(e.target.value)
                      }
                    }}
                    className="text-xs h-8"
                    placeholder="3"
                  />
                </div>

                <div className="flex-1 min-w-[150px]">
                  <label htmlFor="min-refuel" className="text-xs font-medium">
                    Min Refuel (gal)
                  </label>
                  <Input
                    id="min-refuel"
                    type="number"
                    min="0"
                    step="0.1"
                    value={minRefuelGallons}
                    onChange={(e) => setMinRefuelGallons(e.target.value)}
                    className="text-xs h-8"
                    placeholder="Optional"
                  />
                </div>

                <div className="flex-1 min-w-[200px]">
                  <div className="flex justify-between items-center mb-1">
                    <label htmlFor="max-detour" className="text-xs font-medium">
                      Max Detour (km)
                    </label>
                    <span className="text-xs font-semibold text-muted-foreground">
                      {(parseInt(maxDetourMeters, 10) / 1000).toFixed(0)}km
                    </span>
                  </div>
                  <div className="flex gap-2 items-center">
                    <button
                      type="button"
                      onClick={() => {
                        const current = parseInt(maxDetourMeters, 10)
                        const newValue = Math.max(0, current - 1000)
                        setMaxDetourMeters(String(newValue))
                      }}
                      className="px-2 py-1 h-8 rounded border border-border bg-muted hover:bg-muted/80 text-xs font-medium transition-colors"
                      disabled={parseInt(maxDetourMeters, 10) === 0}
                      aria-label="Decrease detour distance"
                    >
                      −
                    </button>
                    <input
                      id="max-detour"
                      type="range"
                      min="0"
                      max="100000"
                      step="1000"
                      value={maxDetourMeters}
                      onChange={(e) => setMaxDetourMeters(e.target.value)}
                      className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const current = parseInt(maxDetourMeters, 10)
                        const newValue = Math.min(100000, current + 1000)
                        setMaxDetourMeters(String(newValue))
                      }}
                      className="px-2 py-1 h-8 rounded border border-border bg-muted hover:bg-muted/80 text-xs font-medium transition-colors"
                      disabled={parseInt(maxDetourMeters, 10) === 100000}
                      aria-label="Increase detour distance"
                    >
                      +
                    </button>
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground mt-1">
                    <span>0</span>
                    <span>100km</span>
                  </div>
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
            </FloatingPanel>
          )}
        </div>
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
        <MeasureTool mapInstance={mapInstance} />
        <LayerTogglePanel
          visibleLayers={visibleLayers}
          onToggleLayer={handleToggleLayer}
          counts={{
            traffic: traffic?.incidents?.length ?? 0,
            fuel: fuelStations.length,
            "truck-restrictions": truckRestrictions.length,
            "rest-areas": restAreas?.features?.length ?? 0,
            "optimization-stops": optimizationSteps.length,
            "optimization-rejected":
              optimizationResult?.explanation.skipped_station_stats?.reduce(
                (sum, stat) => sum + stat.count,
                0,
              ) ?? 0,
          }}
        />
        {visibleLayers.has("route") && (
          <RouteLayer
            mapInstance={mapInstance}
            coordinates={routeCoordinates}
          />
        )}
        {optimizationSteps.length > 0 && routeCoordinates && (
          <ReachableRouteLayer
            mapInstance={mapInstance}
            coordinates={routeCoordinates}
            activeStep={activeOptimizationStep}
            consumptionMpg={Number(
              vehicles.find((v) => v.id === optimizationResult?.vehicle_id)
                ?.consumption_mpg,
            )}
            routeTotalDistanceMeters={routeTotalDistanceMeters}
            reserveGallons={optimizationReserveGallons}
          />
        )}
        {visibleLayers.has("detour") && (
          <DetourLayer
            mapInstance={mapInstance}
            coordinates={routeCoordinates}
            detourMeters={parseInt(maxDetourMeters, 10)}
          />
        )}
        {visibleLayers.has("traffic") && (
          <TrafficLayer mapInstance={mapInstance} traffic={traffic} />
        )}
        {visibleLayers.has("fuel") && (
          <FuelLayer
            mapInstance={mapInstance}
            stations={fuelStations}
            activeFuelStationIds={activeFuelStationIds}
          />
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
        {visibleLayers.has("optimization-stops") &&
          optimizationSteps.length > 0 && (
            <OptimizationStopsLayer
              mapInstance={mapInstance}
              steps={optimizationSteps}
              activeStepIndex={activeStepIndex}
            />
          )}
        {visibleLayers.has("optimization-rejected") && optimizationResult && (
          <OptimizationRejectedStationsLayer
            mapInstance={mapInstance}
            skippedStationStats={
              optimizationResult.explanation.skipped_station_stats ?? []
            }
            activeStep={activeOptimizationStep}
            maxAllowedDetourMeters={parseInt(maxDetourMeters, 10) || null}
          />
        )}
        {comparisonOpen && activeOptimizationStep?.selection && (
          <OptimizationComparedStationsLayer
            mapInstance={mapInstance}
            alternatives={activeOptimizationStep.selection.alternatives ?? []}
          />
        )}
        {optimizationSteps.length > 0 && (
          <OptimizationWalkthrough
            steps={optimizationSteps}
            optimization={optimizationResult}
            activeStepIndex={activeStepIndex}
            onStepChange={handleStepChange}
            failure={optimizationResult?.failure ?? null}
            economics={optimizationResult?.economics}
            onComparisonOpenChange={setComparisonOpen}
            onFocusStation={(coordinate) => mapRef.current?.panTo(coordinate)}
            consumptionMpg={
              vehicles.find((v) => v.id === optimizationResult?.vehicle_id)
                ?.consumption_mpg
            }
            summary={optimizationResult?.summary}
            routeTotalDistanceMeters={routeTotalDistanceMeters}
            reserveGallons={optimizationReserveGallons}
            explainPortalContainer={mapContainerRef.current}
            usableTankGallons={
              vehicles.find((v) => v.id === optimizationResult?.vehicle_id)
                ?.usable_tank_capacity_gallons
            }
          />
        )}
      </div>
    </div>
  )
}
