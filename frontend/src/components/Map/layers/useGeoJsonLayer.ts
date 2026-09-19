/**
 * useGeoJsonLayer hook
 *
 * Manages the lifecycle of a MapLibre GeoJSON source and its layers.
 *
 * Every map layer (route, traffic, fuel, truck restrictions) owns exactly one
 * source and one or more layers, so the add/update/remove logic is shared here
 * instead of being duplicated per layer component.
 */

import type { Feature, FeatureCollection } from "geojson"
import type { LayerSpecification, Map as MapLibreMap } from "maplibre-gl"
import { useEffect } from "react"

export type GeoJsonData = FeatureCollection | Feature

interface UseGeoJsonLayerOptions {
  /** MapLibre map instance, null until the map is ready */
  mapInstance: MapLibreMap | null
  /** Unique source id */
  sourceId: string
  /** Layer specifications built for the given source */
  buildLayers: (sourceId: string) => LayerSpecification[]
  /** GeoJSON payload, null removes the layer */
  data: GeoJsonData | null
}

/**
 * Run a callback once the map style is ready.
 *
 * Sources cannot be added before the style has loaded, so calls made during
 * initial render are deferred to the `load` event.
 */
function whenStyleReady(map: MapLibreMap, callback: () => void): () => void {
  if (map.isStyleLoaded()) {
    callback()
    return () => {}
  }

  map.once("load", callback)
  return () => {
    map.off("load", callback)
  }
}

/**
 * Attach a GeoJSON source and its layers to the map.
 *
 * Updates the source data in place when it already exists and removes both
 * layers and source on unmount or when `data` becomes null.
 */
export function useGeoJsonLayer({
  mapInstance,
  sourceId,
  buildLayers,
  data,
}: UseGeoJsonLayerOptions): void {
  useEffect(() => {
    if (!mapInstance) {
      return
    }

    const layers = buildLayers(sourceId)

    const remove = () => {
      try {
        for (const layer of layers) {
          if (mapInstance.getLayer(layer.id)) {
            mapInstance.removeLayer(layer.id)
          }
        }
        if (mapInstance.getSource(sourceId)) {
          mapInstance.removeSource(sourceId)
        }
      } catch (error) {
        console.error(`Error removing layer "${sourceId}"`, error)
      }
    }

    if (!data) {
      remove()
      return
    }

    const apply = () => {
      try {
        const existing = mapInstance.getSource(sourceId)

        if (existing && "setData" in existing) {
          ;(existing as { setData: (value: GeoJsonData) => void }).setData(data)
        } else {
          mapInstance.addSource(sourceId, { type: "geojson", data })
        }

        for (const layer of layers) {
          if (!mapInstance.getLayer(layer.id)) {
            mapInstance.addLayer(layer)
          }
        }
      } catch (error) {
        console.error(`Error updating layer "${sourceId}"`, error)
      }
    }

    const cancel = whenStyleReady(mapInstance, apply)

    return () => {
      cancel()
      remove()
    }
  }, [mapInstance, sourceId, data, buildLayers])
}
