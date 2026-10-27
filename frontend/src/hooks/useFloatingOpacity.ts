/**
 * Opacity shared by all floating map elements. Stored in localStorage and
 * exposed as the CSS variable `--floating-opacity` on the map container, so
 * every floating element (and portals rendered inside it) follows one value.
 */

import { useSyncExternalStore } from "react"

const STORAGE_KEY = "floating-opacity"
const DEFAULT_OPACITY = 1
const MIN_OPACITY = 0.2
const listeners = new Set<() => void>()

function clampOpacity(value: number): number {
  return Math.min(1, Math.max(MIN_OPACITY, value))
}

function readOpacity(): number {
  try {
    const stored = Number(localStorage.getItem(STORAGE_KEY))
    return localStorage.getItem(STORAGE_KEY) === null
      ? DEFAULT_OPACITY
      : clampOpacity(stored)
  } catch {
    return DEFAULT_OPACITY
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  window.addEventListener("storage", listener)
  return () => {
    listeners.delete(listener)
    window.removeEventListener("storage", listener)
  }
}

export function setFloatingOpacity(value: number): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(clampOpacity(value)))
  } catch {
    // Storage unavailable: the value then only lasts until reload.
  }
  for (const listener of listeners) listener()
}

export const FLOATING_OPACITY_MIN = MIN_OPACITY

export function useFloatingOpacity(): number {
  return useSyncExternalStore(subscribe, readOpacity, () => DEFAULT_OPACITY)
}
