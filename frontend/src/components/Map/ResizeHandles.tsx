import type { PointerEvent as ReactPointerEvent } from "react"
import type { ResizeEdge } from "@/hooks/useResizable"

const HANDLES: { edge: ResizeEdge; className: string; cursor: string }[] = [
  { edge: "n", className: "top-0 left-2 right-2 h-1.5", cursor: "ns-resize" },
  {
    edge: "s",
    className: "bottom-0 left-2 right-2 h-1.5",
    cursor: "ns-resize",
  },
  { edge: "w", className: "left-0 top-2 bottom-2 w-1.5", cursor: "ew-resize" },
  { edge: "e", className: "right-0 top-2 bottom-2 w-1.5", cursor: "ew-resize" },
  { edge: "nw", className: "top-0 left-0 h-3 w-3", cursor: "nwse-resize" },
  { edge: "ne", className: "top-0 right-0 h-3 w-3", cursor: "nesw-resize" },
  { edge: "sw", className: "bottom-0 left-0 h-3 w-3", cursor: "nesw-resize" },
  { edge: "se", className: "bottom-0 right-0 h-3 w-3", cursor: "nwse-resize" },
]

interface ResizeHandlesProps {
  onResizeStart: (
    edge: ResizeEdge,
    event: ReactPointerEvent<HTMLElement>,
  ) => void
}

/**
 * Invisible edge and corner handles for a floating panel. The panel must be
 * `relative`. Handles carry `data-no-drag` so dragging the panel body ignores them.
 */
export function ResizeHandles({ onResizeStart }: ResizeHandlesProps) {
  return (
    <>
      {HANDLES.map(({ edge, className, cursor }) => (
        <div
          key={edge}
          data-no-drag
          data-resize-handle={edge}
          onPointerDown={(event) => onResizeStart(edge, event)}
          style={{ cursor, touchAction: "none" }}
          className={`absolute z-10 ${className}`}
        />
      ))}
    </>
  )
}
