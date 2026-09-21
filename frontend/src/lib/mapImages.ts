import type { Map as MapLibreMap } from "maplibre-gl"

export interface MapImageDefinition {
  id: string
  svg: string
}

/**
 * Ensures symbol images exist once the style is ready and after any style refresh.
 *
 * MapLibre symbol layers silently fail to render while referenced images are still
 * missing, so we keep retrying on style lifecycle events until all images are
 * present.
 */
export function syncMapImages(
  mapInstance: MapLibreMap | null,
  images: MapImageDefinition[],
): () => void {
  if (!mapInstance) {
    return () => {}
  }

  let disposed = false
  const pendingImageIds = new Set<string>()

  const ensureImages = () => {
    if (disposed || !mapInstance.isStyleLoaded()) {
      return
    }

    for (const { id, svg } of images) {
      if (mapInstance.hasImage(id) || pendingImageIds.has(id)) {
        continue
      }

      pendingImageIds.add(id)

      const img = new Image()
      img.onload = () => {
        pendingImageIds.delete(id)

        if (disposed || mapInstance.hasImage(id)) {
          return
        }

        mapInstance.addImage(id, img)
        mapInstance.triggerRepaint()
      }
      img.onerror = () => {
        pendingImageIds.delete(id)
        console.error(`[mapImages] Failed to load image: ${id}`)
      }
      img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
    }
  }

  ensureImages()
  mapInstance.on("load", ensureImages)
  mapInstance.on("styledata", ensureImages)

  return () => {
    disposed = true
    mapInstance.off("load", ensureImages)
    mapInstance.off("styledata", ensureImages)
  }
}
