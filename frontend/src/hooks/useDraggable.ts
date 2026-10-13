import type { PointerEvent as ReactPointerEvent, RefObject } from "react"
import { useCallback, useEffect, useRef, useState } from "react"

const INTERACTIVE_SELECTOR =
  "button, input, select, textarea, a, label, [role='button'], [data-no-drag]"

interface Offset {
  x: number
  y: number
}

/**
 * Makes an absolutely positioned overlay draggable within its offset parent
 * (the map container). Dragging starts from any non-interactive area of the
 * element, and the element is clamped so it cannot leave the parent.
 */
export function useDraggable<T extends HTMLElement>(
  ref: RefObject<T | null>,
  boundsRef?: RefObject<HTMLElement | null>,
) {
  const [offset, setOffset] = useState<Offset>({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const dragRef = useRef<{
    pointerId: number
    lastX: number
    lastY: number
  } | null>(null)

  const onPointerDown = useCallback((event: ReactPointerEvent<T>) => {
    if (event.button !== 0) return
    const target = event.target as HTMLElement
    if (target.closest(INTERACTIVE_SELECTOR)) return
    dragRef.current = {
      pointerId: event.pointerId,
      lastX: event.clientX,
      lastY: event.clientY,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
    setIsDragging(true)
  }, [])

  useEffect(() => {
    if (!isDragging) return

    const onMove = (event: PointerEvent) => {
      const drag = dragRef.current
      const element = ref.current
      if (!drag || !element || event.pointerId !== drag.pointerId) return

      let dx = event.clientX - drag.lastX
      let dy = event.clientY - drag.lastY
      drag.lastX = event.clientX
      drag.lastY = event.clientY

      const parent =
        boundsRef?.current ?? (element.offsetParent as HTMLElement | null)
      if (parent) {
        const rect = element.getBoundingClientRect()
        const bounds = parent.getBoundingClientRect()
        dx = Math.min(
          Math.max(dx, bounds.left - rect.left),
          bounds.right - rect.right,
        )
        dy = Math.min(
          Math.max(dy, bounds.top - rect.top),
          bounds.bottom - rect.bottom,
        )
      }

      setOffset((current) => ({ x: current.x + dx, y: current.y + dy }))
    }

    const onUp = (event: PointerEvent) => {
      if (dragRef.current?.pointerId !== event.pointerId) return
      dragRef.current = null
      setIsDragging(false)
    }

    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
    window.addEventListener("pointercancel", onUp)
    return () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
      window.removeEventListener("pointercancel", onUp)
    }
  }, [isDragging, ref, boundsRef])

  return {
    dragHandlers: { onPointerDown },
    dragStyle: {
      transform: `translate(${offset.x}px, ${offset.y}px)`,
      cursor: isDragging ? "grabbing" : undefined,
      userSelect: isDragging ? ("none" as const) : undefined,
    },
  }
}
