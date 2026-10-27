import type { PointerEvent as ReactPointerEvent } from "react"
import { useSyncExternalStore } from "react"

const BASE_Z_INDEX = 10

const zIndexByPanel = new Map<string, number>()
const listeners = new Set<() => void>()
let topZIndex = BASE_Z_INDEX

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function raisePanel(panelId: string) {
  if (zIndexByPanel.get(panelId) === topZIndex) return
  topZIndex += 1
  zIndexByPanel.set(panelId, topZIndex)
  for (const listener of listeners) {
    listener()
  }
}

/**
 * Stacking order for floating map panels. A panel that the user interacts
 * with is raised above the others, so its dropdowns are not covered.
 */
export function usePanelStack(panelId: string) {
  const zIndex = useSyncExternalStore(
    subscribe,
    () => zIndexByPanel.get(panelId) ?? BASE_Z_INDEX,
    () => BASE_Z_INDEX,
  )

  const onPointerDownCapture = (_event: ReactPointerEvent<HTMLElement>) => {
    raisePanel(panelId)
  }

  return { zIndex, onPointerDownCapture }
}
