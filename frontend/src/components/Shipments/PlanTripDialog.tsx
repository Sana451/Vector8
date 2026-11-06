import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Route as RouteIcon } from "lucide-react"
import { useState } from "react"

import { ShipmentsService, type VehicleSuggestion } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

const METERS_PER_MILE = 1609.344
const MAX_LONGITUDE = 180
const MAX_LATITUDE = 90

// Lets only digits, one dot and a leading minus through; a comma is read as a dot.
// Returns null for rejected input so the caller keeps the previous value.
function sanitizeCoordinateInput(value: string): string | null {
  const normalized = value.replace(",", ".")
  return /^-?\d*\.?\d*$/.test(normalized) ? normalized : null
}

function parseCoordinate(value: string, limit: number): number | null {
  if (value === "" || value === "-" || value === ".") {
    return null
  }
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || Math.abs(parsed) > limit) {
    return null
  }
  return parsed
}

function describeDistance(suggestion: VehicleSuggestion): string {
  const meters = suggestion.distance_to_pickup_meters
  if (meters === null || meters === undefined) return "No position recorded"
  const miles = Math.round(meters / METERS_PER_MILE)
  const stale = suggestion.is_position_stale ? " (position is old)" : ""
  return `${miles} mi to pickup${stale}`
}

interface PlanTripDialogProps {
  shipmentId: string
  disabled?: boolean
}

export default function PlanTripDialog({
  shipmentId,
  disabled,
}: PlanTripDialogProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [vehicleId, setVehicleId] = useState("")

  const [fuel, setFuel] = useState("")
  const [longitude, setLongitude] = useState("")
  const [latitude, setLatitude] = useState("")
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: suggestions = [], isLoading } = useQuery({
    queryKey: ["shipment-vehicle-suggestions", shipmentId],
    queryFn: async () =>
      (
        await ShipmentsService.suggestVehicles({
          path: { shipment_id: shipmentId },
        })
      ).data?.data ?? [],
    enabled: isOpen,
  })

  const selected = suggestions.find((row) => row.vehicle_id === vehicleId)
  const needsOrigin = selected !== undefined && !selected.position_source
  const lon = parseCoordinate(longitude, MAX_LONGITUDE)
  const lat = parseCoordinate(latitude, MAX_LATITUDE)
  const lonError =
    needsOrigin && longitude !== "" && lon === null
      ? `Longitude must be between -${MAX_LONGITUDE} and ${MAX_LONGITUDE}`
      : null
  const latError =
    needsOrigin && latitude !== "" && lat === null
      ? `Latitude must be between -${MAX_LATITUDE} and ${MAX_LATITUDE}`
      : null
  const originValid = !needsOrigin || (lon !== null && lat !== null)
  const fuelValid = fuel !== "" && Number(fuel) >= 0

  const mutation = useMutation({
    mutationFn: async () =>
      (
        await ShipmentsService.planShipment({
          path: { shipment_id: shipmentId },
          body: {
            vehicle_id: vehicleId,
            initial_fuel_gallons: fuel,
            origin:
              needsOrigin && lon !== null && lat !== null ? [lon, lat] : null,
          },
        })
      ).data,
    onSuccess: (trip) => {
      showSuccessToast("Trip planned.")
      setIsOpen(false)
      queryClient.invalidateQueries({ queryKey: ["shipments"] })
      queryClient.invalidateQueries({ queryKey: ["shipment", shipmentId] })
      queryClient.invalidateQueries({ queryKey: ["trip-plans"] })
      if (trip) {
        navigate({ to: "/trips/$tripId", params: { tripId: trip.id } })
      }
    },
    onError: (error: Error) => handleError.call(showErrorToast, error),
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button disabled={disabled}>
          <RouteIcon className="size-4" />
          Plan trip
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Plan a trip</DialogTitle>
          <DialogDescription>
            Pick a vehicle. The route starts where it is now, passes the pickup,
            and ends at the last stop, with fuel stops optimised along the way.
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-64 space-y-2 overflow-y-auto">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading vehicles…</p>
          ) : suggestions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No active vehicles.</p>
          ) : (
            suggestions.map((row) => (
              <button
                key={row.vehicle_id}
                type="button"
                onClick={() => setVehicleId(row.vehicle_id)}
                className={cn(
                  "flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-accent",
                  vehicleId === row.vehicle_id && "border-primary bg-accent",
                )}
              >
                <span>
                  <span className="font-medium">{row.name}</span>{" "}
                  <span className="text-muted-foreground">
                    {row.unit_number}
                  </span>
                  {row.position_label ? (
                    <span className="block text-xs text-muted-foreground">
                      {row.position_label}
                    </span>
                  ) : null}
                </span>
                <span className="text-xs text-muted-foreground">
                  {describeDistance(row)}
                </span>
              </button>
            ))
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="plan-fuel">Fuel on board now (gallons)</Label>
          <Input
            id="plan-fuel"
            type="number"
            min="0"
            value={fuel}
            onChange={(event) => setFuel(event.target.value)}
          />
        </div>

        {needsOrigin ? (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              This vehicle has no recorded position. Enter where it starts.
            </p>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label htmlFor="plan-lon">Longitude</Label>
                <Input
                  id="plan-lon"
                  type="text"
                  inputMode="decimal"
                  placeholder="-86.4798"
                  aria-invalid={lonError !== null}
                  value={longitude}
                  onChange={(event) => {
                    const next = sanitizeCoordinateInput(event.target.value)
                    if (next !== null) setLongitude(next)
                  }}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="plan-lat">Latitude</Label>
                <Input
                  id="plan-lat"
                  type="text"
                  inputMode="decimal"
                  placeholder="42.1156"
                  aria-invalid={latError !== null}
                  value={latitude}
                  onChange={(event) => {
                    const next = sanitizeCoordinateInput(event.target.value)
                    if (next !== null) setLatitude(next)
                  }}
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Decimal degrees. Longitude is negative west of Greenwich (US:
              about -67 to -125), latitude is positive north (US: about 25 to
              49). Use a dot, not a comma.
            </p>
            {lonError || latError ? (
              <p className="text-xs text-destructive">
                {[lonError, latError].filter(Boolean).join(". ")}
              </p>
            ) : null}
          </div>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={() => setIsOpen(false)}>
            Cancel
          </Button>
          <LoadingButton
            loading={mutation.isPending}
            disabled={!vehicleId || !fuelValid || !originValid}
            onClick={() => mutation.mutate()}
          >
            Plan trip
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
