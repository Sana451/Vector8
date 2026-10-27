import type {
  CSSProperties,
  Dispatch,
  PointerEvent as ReactPointerEvent,
  RefObject,
  SetStateAction,
} from "react"
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react"

export type ResizeEdge = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw"

interface Offset {
  x: number
  y: number
}

export interface PanelSize {
  width: number
  height: number
}

interface UseResizableOptions {
  /** Setter of the drag offset, so edges on the left/top can move the panel. */
  setOffset: Dispatch<SetStateAction<Offset>>
  boundsRef?: RefObject<HTMLElement | null>
  minWidth?: number
  minHeight?: number
}

interface ResizeState {
  pointerId: number
  edge: ResizeEdge
  startX: number
  startY: number
  startRect: DOMRect
}

const clamp = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max)

/**
 * Lets the user change width and height of an absolutely positioned overlay
 * from any edge or corner. Size is kept in state; until the first resize the
 * panel keeps its own CSS size.
 */
export function useResizable<T extends HTMLElement>(
  ref: RefObject<T | null>,
  {
    setOffset,
    boundsRef,
    minWidth = 220,
    minHeight = 120,
  }: UseResizableOptions,
) {
  const [size, setSize] = useState<PanelSize | null>(null)
  const [isResizing, setIsResizing] = useState(false)
  const resizeRef = useRef<ResizeState | null>(null)
  // Visual top-left corner the panel should keep while resizing. Panels can be
  // anchored to the right or bottom, so changing the size can move that corner.
  const targetRef = useRef<{ left: number; top: number } | null>(null)

  useLayoutEffect(() => {
    const target = targetRef.current
    const element = ref.current
    if (!target || !element) return
    const rect = element.getBoundingClientRect()
    const dx = target.left - rect.left
    const dy = target.top - rect.top
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return
    setOffset((current) => ({ x: current.x + dx, y: current.y + dy }))
  })

  const startResize = useCallback(
    (edge: ResizeEdge, event: ReactPointerEvent<HTMLElement>) => {
      const element = ref.current
      if (event.button !== 0 || !element) return
      event.preventDefault()
      event.stopPropagation()
      resizeRef.current = {
        pointerId: event.pointerId,
        edge,
        startX: event.clientX,
        startY: event.clientY,
        startRect: element.getBoundingClientRect(),
      }
      event.currentTarget.setPointerCapture(event.pointerId)
      setIsResizing(true)
    },
    [ref],
  )

  useEffect(() => {
    if (!isResizing) return

    const onMove = (event: PointerEvent) => {
      const resize = resizeRef.current
      const element = ref.current
      if (!resize || !element || event.pointerId !== resize.pointerId) return

      const parent =
        boundsRef?.current ?? (element.offsetParent as HTMLElement | null)
      const bounds = parent?.getBoundingClientRect()
      const { startRect: start, edge } = resize
      const dx = event.clientX - resize.startX
      const dy = event.clientY - resize.startY

      let left = start.left
      let top = start.top
      let width = start.width
      let height = start.height

      if (edge.includes("e")) {
        const max = bounds
          ? bounds.right - start.left
          : Number.POSITIVE_INFINITY
        width = clamp(start.width + dx, minWidth, Math.max(minWidth, max))
      }
      if (edge.includes("w")) {
        const minShift = bounds
          ? bounds.left - start.left
          : Number.NEGATIVE_INFINITY
        const shift = clamp(dx, minShift, start.width - minWidth)
        left = start.left + shift
        width = start.width - shift
      }
      if (edge.includes("s")) {
        const max = bounds
          ? bounds.bottom - start.top
          : Number.POSITIVE_INFINITY
        height = clamp(start.height + dy, minHeight, Math.max(minHeight, max))
      }
      if (edge.includes("n")) {
        const minShift = bounds
          ? bounds.top - start.top
          : Number.NEGATIVE_INFINITY
        const shift = clamp(dy, minShift, start.height - minHeight)
        top = start.top + shift
        height = start.height - shift
      }

      targetRef.current = { left, top }
      setSize({ width, height })
    }

    const onUp = (event: PointerEvent) => {
      if (resizeRef.current?.pointerId !== event.pointerId) return
      resizeRef.current = null
      targetRef.current = null
      setIsResizing(false)
    }

    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
    window.addEventListener("pointercancel", onUp)
    return () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
      window.removeEventListener("pointercancel", onUp)
    }
  }, [isResizing, ref, boundsRef, minWidth, minHeight])

  const sizeStyle: CSSProperties = size
    ? { width: size.width, height: size.height }
    : {}

  return { size, sizeStyle, startResize, isResizing }
}
