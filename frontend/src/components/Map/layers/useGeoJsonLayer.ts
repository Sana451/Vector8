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

export type LayerWithVisibility = LayerSpecification & {
  /** Optional: function to determine if layer should be visible based on zoom */
  shouldBeVisible?: (zoom: number) => boolean
}

interface UseGeoJsonLayerOptions {
  /** MapLibre map instance, null until the map is ready */
  mapInstance: MapLibreMap | null
  /** Unique source id */
  sourceId: string
  /** Layer specifications built for the given source (can include shouldBeVisible per layer) */
  buildLayers: (sourceId: string) => LayerWithVisibility[]
  /** GeoJSON payload, null removes the layer */
  data: GeoJsonData | null
  /** Optional: function to determine if layer should be visible based on zoom (applies to all layers) */
  shouldBeVisible?: (zoom: number) => boolean
  /** Optional: enable MapLibre clustering for this source */
  clusterOptions?: {
    enabled: boolean
    radius?: number
    maxZoom?: number
  }
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
  shouldBeVisible,
  clusterOptions,
}: UseGeoJsonLayerOptions): void {
  useEffect(() => {
    if (!mapInstance) {
      console.log(`[useGeoJsonLayer] Waiting for map instance: ${sourceId}`)
      return
    }

    const layers = buildLayers(sourceId)
    console.log(
      `[useGeoJsonLayer] Layers built for ${sourceId}:`,
      layers.map((l) => l.id),
    )

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
        console.log(`[useGeoJsonLayer] Applying ${sourceId}:`, {
          hasExistingSource: !!existing,
          data: data ? "has data" : "no data",
          currentZoom: mapInstance.getZoom(),
          isStyleLoaded: mapInstance.isStyleLoaded(),
        })

        if (existing && "setData" in existing) {
          ;(existing as { setData: (value: GeoJsonData) => void }).setData(data)
          console.log(`[useGeoJsonLayer] Updated source data for ${sourceId}`)
        } else {
          const sourceConfig: any = { type: "geojson", data }

          // Add clustering configuration if provided
          if (clusterOptions?.enabled) {
            sourceConfig.cluster = true
            sourceConfig.clusterRadius = clusterOptions.radius ?? 50
            sourceConfig.clusterMaxZoom = clusterOptions.maxZoom ?? 14
            console.log(
              `[useGeoJsonLayer] Creating clustered source ${sourceId}`,
              clusterOptions,
            )
          }

          mapInstance.addSource(sourceId, sourceConfig)
          console.log(`[useGeoJsonLayer] Created source ${sourceId}`)
        }

        for (const layer of layers) {
          if (!mapInstance.getLayer(layer.id)) {
            mapInstance.addLayer(layer)
            console.log(`[useGeoJsonLayer] Added layer ${layer.id}`)
          }
        }

        // Apply zoom-dependent visibility AFTER layers are added
        const currentZoom = mapInstance.getZoom()
        console.log(`[useGeoJsonLayer] Current zoom: ${currentZoom}`)

        for (const layer of layers) {
          if (mapInstance.getLayer(layer.id)) {
            let shouldShow = true

            // First check layer-specific visibility
            const layerWithVisibility = layer as LayerWithVisibility
            if (layerWithVisibility.shouldBeVisible) {
              shouldShow = layerWithVisibility.shouldBeVisible(currentZoom)
            }
            // Then apply global visibility if layer didn't restrict it
            else if (shouldBeVisible) {
              shouldShow = shouldBeVisible(currentZoom)
            }

            const visibility: "visible" | "none" = shouldShow
              ? "visible"
              : "none"
            mapInstance.setLayoutProperty(layer.id, "visibility", visibility)
            console.log(
              `[useGeoJsonLayer] Set ${layer.id} visibility to ${visibility} (zoom=${currentZoom})`,
            )
          }
        }
      } catch (error) {
        console.error(`Error updating layer "${sourceId}"`, error)
      }
    }

    const cancel = whenStyleReady(mapInstance, apply)
    mapInstance.on("styledata", apply)

    // Handle zoom changes for visibility
    const handleZoomChange = () => {
      if (!mapInstance.getSource(sourceId)) {
        return
      }

      const currentZoom = mapInstance.getZoom()
      console.log(
        `[useGeoJsonLayer] Zoom changed to ${currentZoom} for ${sourceId}`,
      )

      for (const layer of layers) {
        if (mapInstance.getLayer(layer.id)) {
          let shouldShow = true

          // First check layer-specific visibility
          const layerWithVisibility = layer as LayerWithVisibility
          if (layerWithVisibility.shouldBeVisible) {
            shouldShow = layerWithVisibility.shouldBeVisible(currentZoom)
          }
          // Then apply global visibility if layer didn't restrict it
          else if (shouldBeVisible) {
            shouldShow = shouldBeVisible(currentZoom)
          }

          mapInstance.setLayoutProperty(
            layer.id,
            "visibility",
            shouldShow ? "visible" : "none",
          )
        }
      }
    }

    mapInstance.on("zoom", handleZoomChange)

    return () => {
      cancel()
      mapInstance.off("styledata", apply)
      mapInstance.off("zoom", handleZoomChange)
      remove()
    }
  }, [
    mapInstance,
    sourceId,
    data,
    buildLayers,
    shouldBeVisible,
    clusterOptions,
  ])
}
