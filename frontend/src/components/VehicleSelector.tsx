import type { RefObject } from "react"
import type { VehiclePublic } from "@/client"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { formatRoutingSummary } from "@/lib/vehicleRouting"

interface VehicleSelectorProps {
  vehicles: VehiclePublic[]
  selectedVehicleId: string
  onSelectVehicle: (vehicleId: string) => void
  disabled?: boolean
  /** Element the list is portaled into, so it is not clipped by the host panel. */
  containerRef?: RefObject<HTMLElement | null>
}

const formatNumber = (value: unknown, decimals: number): string => {
  if (typeof value === "number") {
    return value.toFixed(decimals)
  }
  if (typeof value === "string") {
    return parseFloat(value).toFixed(decimals)
  }
  return String(value)
}

export function VehicleSelector({
  vehicles,
  selectedVehicleId,
  onSelectVehicle,
  disabled = false,
  containerRef,
}: VehicleSelectorProps) {
  const selectedVehicle = vehicles.find((v) => v.id === selectedVehicleId)

  return (
    <div className="flex-1 min-w-[200px]">
      <label htmlFor="vehicle-select" className="text-xs font-medium">
        Vehicle
      </label>
      <Select
        value={selectedVehicleId || undefined}
        onValueChange={(value) => onSelectVehicle(value)}
        disabled={disabled || vehicles.length === 0}
      >
        <SelectTrigger id="vehicle-select" className="w-full">
          <SelectValue
            placeholder={
              vehicles.length === 0 ? "No vehicles yet" : "Select a vehicle..."
            }
          >
            {selectedVehicle
              ? `${selectedVehicle.name} (${selectedVehicle.unit_number})`
              : undefined}
          </SelectValue>
        </SelectTrigger>
        {vehicles.length > 0 && (
          <SelectContent portalContainer={containerRef?.current}>
            {vehicles.map((vehicle) => {
              const summary = formatRoutingSummary(vehicle)
              return (
                <SelectItem key={vehicle.id} value={vehicle.id}>
                  <div className="flex flex-col">
                    <span className="font-medium">
                      {vehicle.name} ({vehicle.unit_number})
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {summary && <span className="block">{summary}</span>}
                      <span className="block">
                        Tank: {formatNumber(vehicle.tank_capacity_gallons, 1)}{" "}
                        gal · Usable:{" "}
                        {formatNumber(vehicle.usable_tank_capacity_gallons, 2)}{" "}
                        gal · {formatNumber(vehicle.consumption_mpg, 2)} MPG
                      </span>
                    </span>
                  </div>
                </SelectItem>
              )
            })}
          </SelectContent>
        )}
      </Select>
    </div>
  )
}
