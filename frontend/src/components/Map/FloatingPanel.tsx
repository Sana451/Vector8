import { ChevronDown, ChevronUp } from "lucide-react"
import { type ReactNode, type RefObject, useRef, useState } from "react"
import { ResizeHandles } from "@/components/Map/ResizeHandles"
import { useDraggable } from "@/hooks/useDraggable"
import { usePanelStack } from "@/hooks/usePanelStack"
import { useResizable } from "@/hooks/useResizable"

interface FloatingPanelProps {
  title: string
  boundsRef: RefObject<HTMLElement | null>
  /** Shown next to the title while collapsed (e.g. route summary). */
  collapsedSummary?: ReactNode
  /** Starting position inside the bounds; panels are positioned independently. */
  initialPosition: { left: number; top: number }
  /** Width before the user resizes the panel; ignored while collapsed. */
  defaultWidth?: number
  children: ReactNode
}

export function FloatingPanel({
  title,
  boundsRef,
  collapsedSummary,
  initialPosition,
  defaultWidth,
  children,
}: FloatingPanelProps) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const { dragHandlers, dragStyle, setOffset } = useDraggable(
    panelRef,
    boundsRef,
  )
  const { sizeStyle, startResize } = useResizable(panelRef, {
    setOffset,
    boundsRef,
  })
  const { zIndex, onPointerDownCapture } = usePanelStack(`floating:${title}`)

  return (
    <div
      ref={panelRef}
      {...dragHandlers}
      onPointerDownCapture={onPointerDownCapture}
      style={{
        ...dragStyle,
        ...(isCollapsed || defaultWidth === undefined
          ? {}
          : { width: defaultWidth }),
        ...(isCollapsed ? {} : sizeStyle),
        zIndex,
        opacity: "var(--floating-opacity, 1)",
        left: initialPosition.left,
        top: initialPosition.top,
        maxWidth: "calc(100vw - 2rem)",
      }}
      className={`pointer-events-auto absolute flex flex-col cursor-grab rounded-lg border border-border/70 bg-background p-2 shadow-md ${isCollapsed ? "" : "w-[min(760px,calc(100vw-2rem))] max-h-[calc(100vh-2rem)]"}`}
    >
      {!isCollapsed && <ResizeHandles onResizeStart={startResize} />}
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold">{title}</span>
        {isCollapsed && collapsedSummary}
        <button
          type="button"
          onClick={() => setIsCollapsed((value) => !value)}
          aria-expanded={!isCollapsed}
          aria-label={isCollapsed ? `Expand ${title}` : `Collapse ${title}`}
          className="ml-auto flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
        >
          {isCollapsed ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronUp className="h-4 w-4" />
          )}
        </button>
      </div>
      <div
        className={
          isCollapsed
            ? "hidden"
            : "mt-2 min-h-0 flex-1 overflow-auto cursor-auto"
        }
      >
        {children}
      </div>
    </div>
  )
}
