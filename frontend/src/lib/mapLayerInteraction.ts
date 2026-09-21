/**
 * Map layer visibility and interaction utilities
 *
 * Handles zoom-dependent visibility and interactive marker effects
 */

/**
 * Straightforward zoom rules shared by all object layers.
 *
 * - zoom < 8: only the route is visible
 * - zoom 8-13: clustered view + standalone objects outside clusters
 * - zoom 14+: individual objects only, no clusters
 */
export const mapObjectZoom = {
  objects: 8,
  detailed: 14,
  clusterMax: 13,
} as const

export type MapObjectVisibilityMode = "route-only" | "clustered" | "individual"

export function getVisibilityForZoom(zoom: number): MapObjectVisibilityMode {
  if (zoom < mapObjectZoom.objects) {
    return "route-only"
  }
  if (zoom < mapObjectZoom.detailed) {
    return "clustered"
  }
  return "individual"
}

export function shouldShowMapObjects(zoom: number): boolean {
  return zoom >= mapObjectZoom.objects
}

export function shouldShowClusters(zoom: number): boolean {
  return zoom >= mapObjectZoom.objects && zoom < mapObjectZoom.detailed
}

export function shouldShowObjectLabels(zoom: number): boolean {
  return zoom >= mapObjectZoom.detailed
}

/**
 * Paint/layout properties for hover and selected states
 * Uses MapLibre feature state for interactivity
 */
export const interactionStyles = {
  /**
   * Hover ring: white 3px stroke around marker
   * Apply as: "circle-stroke-color": hoverRing.strokeColor
   *           "circle-stroke-width": hoverRing.strokeWidth
   */
  hoverRing: {
    strokeColor: "#ffffff",
    strokeWidth: 3,
    opacity: 0.8,
  },

  /**
   * Selected marker: enlarge by 25%
   * Use in paint properties as:
   * "circle-radius": ["case", ["feature-state", "hover"], baseSizeMultiplier * 1.25, baseSizeMultiplier]
   */
  selectedScale: 1.25,

  /**
   * Active layer glow: subtle shadow/blur effect
   * For symbol layers, use icon-opacity
   */
  glowOpacity: 1.0,
  normalOpacity: 0.8,
}

/**
 * Helper to create zoom-dependent expressions for layer visibility
 *
 * Example usage in layer paint property:
 * "circle-opacity": createZoomVisibility(8, 11, 14)
 *
 * Returns:
 * - 0 at zoom < 8
 * - 0.5 at zoom 8-10 (cluster view)
 * - 1.0 at zoom >= 11 (detailed view)
 */
export function createZoomVisibility(
  clusterStartZoom: number,
  detailedStartZoom: number,
): any {
  return [
    "step",
    ["zoom"],
    0, // Before cluster start: hidden
    clusterStartZoom,
    0.5, // At cluster zoom: semi-visible (cluster mode)
    detailedStartZoom,
    1.0, // At detailed zoom: fully visible
  ]
}

/**
 * Helper to create hover/selected state expressions
 *
 * Used in layer properties to apply visual effects on interaction:
 * "circle-radius": [
 *   "case",
 *   ["feature-state", "hover"],
 *   hoverSize,
 *   ["feature-state", "selected"],
 *   selectedSize,
 *   defaultSize
 * ]
 */
export function createHoverSelectedExpression(
  defaultValue: any,
  hoverValue: any,
  selectedValue: any,
): any {
  return [
    "case",
    ["feature-state", "hover"],
    hoverValue,
    ["feature-state", "selected"],
    selectedValue,
    defaultValue,
  ]
}

/**
 * Helper to create glow effect for selected markers
 * Apply to icon-opacity or similar
 */
export function createGlowExpression(
  normalOpacity: number,
  glowOpacity: number,
): any {
  return ["case", ["feature-state", "selected"], glowOpacity, normalOpacity]
}

/**
 * Event handlers for hover/selected states on map
 * Should be called in layer components
 */
export function attachInteractionHandlers(
  mapInstance: any,
  layerId: string,
  onHover?: (feature: any) => void,
  onSelect?: (feature: any) => void,
) {
  const handleMouseEnter = (e: any) => {
    if (!e.features?.[0]) return
    const feature = e.features[0]
    mapInstance.setFeatureState(feature, { hover: true })
    onHover?.(feature)
  }

  const handleMouseLeave = (e: any) => {
    if (!e.features?.[0]) return
    const feature = e.features[0]
    mapInstance.setFeatureState(feature, { hover: false })
  }

  const handleClick = (e: any) => {
    if (!e.features?.[0]) return
    const feature = e.features[0]
    // Toggle selected state
    const isCurrentlySelected = mapInstance.getFeatureState(feature).selected
    mapInstance.setFeatureState(feature, { selected: !isCurrentlySelected })
    onSelect?.(feature)
  }

  mapInstance.on("mouseenter", layerId, handleMouseEnter)
  mapInstance.on("mouseleave", layerId, handleMouseLeave)
  mapInstance.on("click", layerId, handleClick)

  // Return cleanup function
  return () => {
    mapInstance.off("mouseenter", layerId, handleMouseEnter)
    mapInstance.off("mouseleave", layerId, handleMouseLeave)
    mapInstance.off("click", layerId, handleClick)
  }
}
