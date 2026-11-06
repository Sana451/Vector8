/**
 * useResolvedPoint hook
 *
 * Resolves the map point for a route form field. If the field text matches a
 * selected address (or vehicle position), that location is used directly;
 * otherwise the text is geocoded after a short debounce.
 */

import { useEffect, useState } from "react"

import { searchAddress } from "@/api/map"
import type { GeoJSONPoint } from "@/client"
import type { AddressSelection } from "@/lib/mapRequest"

export function useResolvedPoint(
  text: string,
  selection: AddressSelection | null,
): GeoJSONPoint | null {
  const query = text.trim()
  const selectedLocation =
    selection?.location && selection.formatted_address === query
      ? selection.location
      : null
  const [geocoded, setGeocoded] = useState<GeoJSONPoint | null>(null)

  useEffect(() => {
    if (selectedLocation || query.length < 3) {
      return
    }
    let cancelled = false
    const timer = window.setTimeout(async () => {
      try {
        const result = await searchAddress(query)
        if (!cancelled) {
          setGeocoded(result.location ?? null)
        }
      } catch {
        if (!cancelled) {
          setGeocoded(null)
        }
      }
    }, 400)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [query, selectedLocation])

  if (selectedLocation) {
    return selectedLocation
  }
  return query.length < 3 ? null : geocoded
}
