import { useState } from "react"
import type { VehiclePublic } from "@/client"

interface VehicleSelectorProps {
  vehicles: VehiclePublic[]
  selectedVehicleId: string
  onSelectVehicle: (vehicleId: string) => void
  disabled?: boolean
}

export function VehicleSelector({
  vehicles,
  selectedVehicleId,
  onSelectVehicle,
  disabled = false,
}: VehicleSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)

  const selectedVehicle = vehicles.find((v) => v.id === selectedVehicleId)

  const handleSelect = (vehicleId: string) => {
    onSelectVehicle(vehicleId)
    setIsOpen(false)
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

  return (
    <div className="flex-1 min-w-[200px] relative">
      <label htmlFor="vehicle-select" className="text-xs font-medium">
        Vehicle
      </label>
      <button
        type="button"
        id="vehicle-select"
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
        className="w-full text-xs h-8 px-2 rounded border border-border bg-background hover:bg-muted/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-between"
      >
        <span>
          {selectedVehicle
            ? `${selectedVehicle.name} (${selectedVehicle.unit_number})`
            : "Select a vehicle..."}
        </span>
        <span className="text-xs">▼</span>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 border border-border rounded bg-background shadow-lg z-50 max-h-[300px] overflow-y-auto">
          <button
            type="button"
            onClick={() => {
              handleSelect("")
            }}
            className="w-full text-left px-3 py-2 text-xs hover:bg-muted transition-colors border-b border-border/30"
          >
            Select a vehicle...
          </button>

          {vehicles.map((vehicle) => {
            const fuelProfile = vehicle.fuel_profile
            const isSelected = vehicle.id === selectedVehicleId

            return (
              <div
                key={vehicle.id}
                className={`border-b border-border/30 last:border-b-0 hover:bg-muted/70 transition-colors ${
                  isSelected ? "bg-muted" : ""
                }`}
              >
                <button
                  type="button"
                  onClick={() => handleSelect(vehicle.id)}
                  className="w-full text-left px-3 py-2 focus:outline-none"
                >
                  <div className="font-medium text-xs">
                    {vehicle.name} ({vehicle.unit_number})
                  </div>
                  {fuelProfile && (
                    <div className="text-xs text-muted-foreground mt-0.5">
                      <div>
                        Tank:{" "}
                        {formatNumber(fuelProfile.tank_capacity_gallons, 1)} gal
                      </div>
                      <div>
                        Usable:{" "}
                        {formatNumber(
                          fuelProfile.usable_tank_capacity_gallons,
                          2,
                        )}{" "}
                        gal
                      </div>
                      <div>
                        Consumption:{" "}
                        {formatNumber(fuelProfile.consumption_mpg, 2)} MPG
                      </div>
                    </div>
                  )}
                </button>
              </div>
            )
          })}
        </div>
      )}

      {isOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
          aria-label="Close vehicle selector"
        />
      )}
    </div>
  )
}
