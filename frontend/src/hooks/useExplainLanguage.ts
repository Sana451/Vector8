/**
 * Language of the AI explanations. Stored in localStorage so a choice made
 * once applies to every later request, from any "Explain with AI" button.
 */

import { useSyncExternalStore } from "react"

export type ExplainLanguage = "en" | "ru"

const STORAGE_KEY = "ai-explain-language"
const DEFAULT_LANGUAGE: ExplainLanguage = "en"
const listeners = new Set<() => void>()

function readLanguage(): ExplainLanguage {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored === "ru" || stored === "en" ? stored : DEFAULT_LANGUAGE
  } catch {
    return DEFAULT_LANGUAGE
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

export function setExplainLanguage(language: ExplainLanguage): void {
  try {
    localStorage.setItem(STORAGE_KEY, language)
  } catch {
    // Storage unavailable: the choice then only lasts until reload.
  }
  for (const listener of listeners) listener()
}

export function useExplainLanguage(): ExplainLanguage {
  return useSyncExternalStore(subscribe, readLanguage, () => DEFAULT_LANGUAGE)
}
