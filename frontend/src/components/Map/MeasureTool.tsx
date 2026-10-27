import type { Map as MapLibreMap, MapMouseEvent } from "maplibre-gl"
import { useEffect, useMemo, useRef, useState } from "react"
import { ResizeHandles } from "@/components/Map/ResizeHandles"
import { Button } from "@/components/ui/button"
import { useDraggable } from "@/hooks/useDraggable"
import { usePanelStack } from "@/hooks/usePanelStack"
import { useResizable } from "@/hooks/useResizable"
import {
  formatDistance,
  measureLengthKm,
  shouldAddFreehandPoint,
} from "@/lib/measure"
import type { Coordinate } from "@/lib/routing"
import { MeasureLayer } from "./layers/MeasureLayer"

type Mode = "points" | "freehand"

interface MeasureToolProps {
  mapInstance: MapLibreMap | null
}

export function MeasureTool({ mapInstance }: MeasureToolProps) {
  const [active, setActive] = useState(false)
  const [mode, setMode] = useState<Mode>("points")
  const [points, setPoints] = useState<Coordinate[]>([])
  const drawing = useRef(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const { dragHandlers, dragStyle, setOffset } = useDraggable(panelRef)
  const { sizeStyle, startResize } = useResizable(panelRef, { setOffset })
  const { zIndex, onPointerDownCapture } = usePanelStack("measure-tool")

  useEffect(() => {
    if (!mapInstance || !active) {
      return
    }
    const canvas = mapInstance.getCanvas()
    const previousCursor = canvas.style.cursor
    canvas.style.cursor = "crosshair"

    const toCoord = (e: MapMouseEvent): Coordinate => [
      e.lngLat.lng,
      e.lngLat.lat,
    ]

    const onClick = (e: MapMouseEvent) => {
      if (mode === "points") {
        setPoints((prev) => [...prev, toCoord(e)])
      }
    }
    const onDown = (e: MapMouseEvent) => {
      if (mode !== "freehand") return
      e.preventDefault()
      drawing.current = true
      mapInstance.dragPan.disable()
      setPoints([toCoord(e)])
    }
    const onMove = (e: MapMouseEvent) => {
      if (!drawing.current) return
      const next = toCoord(e)
      setPoints((prev) =>
        shouldAddFreehandPoint(prev[prev.length - 1], next)
          ? [...prev, next]
          : prev,
      )
    }
    const onUp = () => {
      if (!drawing.current) return
      drawing.current = false
      mapInstance.dragPan.enable()
    }

    mapInstance.on("click", onClick)
    mapInstance.on("mousedown", onDown)
    mapInstance.on("mousemove", onMove)
    mapInstance.on("mouseup", onUp)
    return () => {
      mapInstance.off("click", onClick)
      mapInstance.off("mousedown", onDown)
      mapInstance.off("mousemove", onMove)
      mapInstance.off("mouseup", onUp)
      mapInstance.dragPan.enable()
      drawing.current = false
      canvas.style.cursor = previousCursor
    }
  }, [mapInstance, active, mode])

  useEffect(() => {
    if (!active) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setActive(false)
        setPoints([])
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [active])

  const distance = useMemo(() => measureLengthKm(points), [points])

  const toggle = () => {
    setActive((v) => !v)
    setPoints([])
  }
  const changeMode = (next: Mode) => {
    setMode(next)
    setPoints([])
  }

  return (
    <>
      <MeasureLayer
        mapInstance={mapInstance}
        points={active ? points : []}
        showVertices={mode === "points"}
      />
      <div
        ref={panelRef}
        {...dragHandlers}
        onPointerDownCapture={onPointerDownCapture}
        style={{ ...sizeStyle, ...dragStyle, zIndex }}
        className="absolute bottom-4 right-16 flex flex-col gap-1 rounded-md border bg-background p-2 shadow text-xs"
      >
        <ResizeHandles onResizeStart={startResize} />
        <Button
          size="sm"
          variant={active ? "default" : "outline"}
          className="h-7 text-xs"
          onClick={toggle}
        >
          📏 Ruler
        </Button>
        {active && (
          <>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant={mode === "points" ? "default" : "outline"}
                className="h-7 text-xs"
                onClick={() => changeMode("points")}
              >
                Points
              </Button>
              <Button
                size="sm"
                variant={mode === "freehand" ? "default" : "outline"}
                className="h-7 text-xs"
                onClick={() => changeMode("freehand")}
              >
                Freehand
              </Button>
            </div>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs"
                disabled={points.length === 0 || mode === "freehand"}
                onClick={() => setPoints((p) => p.slice(0, -1))}
              >
                Undo
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs"
                disabled={points.length === 0}
                onClick={() => setPoints([])}
              >
                Clear
              </Button>
            </div>
            <div className="font-medium">
              {points.length < 2
                ? mode === "points"
                  ? "Click points on the map"
                  : "Press and drag to draw"
                : formatDistance(distance)}
            </div>
          </>
        )}
      </div>
    </>
  )
}
