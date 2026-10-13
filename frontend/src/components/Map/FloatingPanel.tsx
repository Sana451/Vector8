import { ChevronDown, ChevronUp } from "lucide-react"
import { type ReactNode, type RefObject, useRef, useState } from "react"
import { useDraggable } from "@/hooks/useDraggable"

interface FloatingPanelProps {
  title: string
  boundsRef: RefObject<HTMLElement | null>
  /** Shown next to the title while collapsed (e.g. route summary). */
  collapsedSummary?: ReactNode
  children: ReactNode
}

export function FloatingPanel({
  title,
  boundsRef,
  collapsedSummary,
  children,
}: FloatingPanelProps) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const { dragHandlers, dragStyle } = useDraggable(panelRef, boundsRef)

  return (
    <div
      ref={panelRef}
      {...dragHandlers}
      style={dragStyle}
      className="pointer-events-auto w-[min(760px,calc(100vw-2rem))] max-w-full cursor-grab rounded-lg border border-border/70 bg-background p-2 shadow-md"
    >
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
      <div className={isCollapsed ? "hidden" : "mt-2 cursor-auto"}>
        {children}
      </div>
    </div>
  )
}
