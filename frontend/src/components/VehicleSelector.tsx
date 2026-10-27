import { type RefObject, useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import type { VehiclePublic } from "@/client"
import { formatRoutingSummary } from "@/lib/vehicleRouting"

interface VehicleSelectorProps {
  vehicles: VehiclePublic[]
  selectedVehicleId: string
  onSelectVehicle: (vehicleId: string) => void
  disabled?: boolean
  /** Element the list is portaled into, so it is not clipped by the host panel. */
  containerRef?: RefObject<HTMLElement | null>
}

const LIST_MAX_HEIGHT = 300
const MIN_COMFORTABLE_HEIGHT = 160
const GAP = 4

interface ListPlacement {
  left: number
  width: number
  maxHeight: number
  top?: number
  bottom?: number
}

function computePlacement(trigger: HTMLElement): ListPlacement {
  const rect = trigger.getBoundingClientRect()
  const spaceBelow = window.innerHeight - rect.bottom - GAP
  const spaceAbove = rect.top - GAP
  const left = rect.left
  const width = rect.width

  if (spaceBelow >= MIN_COMFORTABLE_HEIGHT || spaceBelow >= spaceAbove) {
    return {
      left,
      width,
      top: rect.bottom + GAP,
      maxHeight: Math.min(LIST_MAX_HEIGHT, spaceBelow),
    }
  }
  return {
    left,
    width,
    bottom: window.innerHeight - rect.top + GAP,
    maxHeight: Math.min(LIST_MAX_HEIGHT, spaceAbove),
  }
}

export function VehicleSelector({
  vehicles,
  selectedVehicleId,
  onSelectVehicle,
  disabled = false,
  containerRef,
}: VehicleSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [placement, setPlacement] = useState<ListPlacement | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node
      if (triggerRef.current?.contains(target)) return
      if (listRef.current?.contains(target)) return
      setIsOpen(false)
    }
    const close = () => setIsOpen(false)
    document.addEventListener("pointerdown", handlePointerDown)
    window.addEventListener("resize", close)
    window.addEventListener("scroll", close, true)
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown)
      window.removeEventListener("resize", close)
      window.removeEventListener("scroll", close, true)
    }
  }, [isOpen])

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
        ref={triggerRef}
        onClick={() => {
          if (!isOpen && triggerRef.current) {
            setPlacement(computePlacement(triggerRef.current))
          }
          setIsOpen(!isOpen)
        }}
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

      {isOpen &&
        placement &&
        createPortal(
          <div
            ref={listRef}
            style={{
              left: placement.left,
              width: placement.width,
              top: placement.top,
              bottom: placement.bottom,
              maxHeight: placement.maxHeight,
            }}
            className="fixed z-[9999] overflow-y-auto rounded border border-border bg-background shadow-lg"
          >
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
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {formatRoutingSummary(vehicle) && (
                        <div>{formatRoutingSummary(vehicle)}</div>
                      )}
                      <div>
                        Tank: {formatNumber(vehicle.tank_capacity_gallons, 1)}{" "}
                        gal
                      </div>
                      <div>
                        Usable:{" "}
                        {formatNumber(vehicle.usable_tank_capacity_gallons, 2)}{" "}
                        gal
                      </div>
                      <div>
                        Consumption: {formatNumber(vehicle.consumption_mpg, 2)}{" "}
                        MPG
                      </div>
                    </div>
                  </button>
                </div>
              )
            })}
          </div>,
          containerRef?.current ?? document.body,
        )}
    </div>
  )
}
