/**
 * Map marker icons as SVG strings
 *
 * Used for proper visual differentiation between layers:
 * - Shape = type of object
 * - Color = state/severity
 * - Size = priority
 */

export const markerIcons = {
  /**
   * Traffic incident triangle markers
   */
  trafficTriangle: (color: string, size: number) => `
    <svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2 L22 20 H2 Z" fill="${color}" stroke="white" stroke-width="1.5"/>
    </svg>
  `,

  /**
   * Fuel station drop markers
   */
  fuelDrop: (color: string) => `
    <svg width="24" height="32" viewBox="0 0 24 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2 C12 2 8 10 8 14 C8 18.418 9.79 22 12 22 C14.21 22 16 18.418 16 14 C16 10 12 2 12 2 Z"
            fill="${color}" stroke="white" stroke-width="1.5"/>
      <circle cx="12" cy="14" r="3" fill="white"/>
    </svg>
  `,

  /**
   * Truck restrictions octagon markers
   */
  restrictionOctagon: (color: string, icon: string) => `
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M10 2 L18 2 L24 8 L24 16 L18 22 L10 22 L4 16 L4 8 Z"
            fill="${color}" stroke="white" stroke-width="1.5"/>
      <text x="14" y="18" text-anchor="middle" font-size="14" font-weight="bold" fill="white">${icon}</text>
    </svg>
  `,

  /**
   * Rest area rounded square markers with content
   */
  restAreaSquare: (color: string, icon: string) => `
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="2" y="2" width="24" height="24" rx="6" fill="${color}" stroke="white" stroke-width="1.5"/>
      <text x="14" y="20" text-anchor="middle" font-size="16" font-weight="bold" fill="white">${icon}</text>
    </svg>
  `,

  /**
   * Cluster markers for Rest Areas
   */
  clusterMarker: (count: number) => `
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="18" cy="18" r="16" fill="#D97706" stroke="white" stroke-width="2"/>
      <text x="18" y="22" text-anchor="middle" font-size="16" font-weight="bold" fill="white">${count}</text>
    </svg>
  `,
}

/**
 * Icon mappings for restriction types
 */
export const restrictionIcons = {
  weight_limit: "⚖",
  height_restriction: "↕",
  no_trucks: "🚫",
  other: "!",
}

/**
 * Icon mappings for rest area types
 */
export const restAreaIcons = {
  "400-4300-0199": "🛏", // Complete Rest Area
  "700-7900-0131": "🅿", // Truck Parking
  default: "🚚",
}

/**
 * Color palettes for each layer
 * Ensures no color conflicts between layers
 */
export const colorPalette = {
  route: "#2563EB",

  traffic: {
    severe: "#B91C1C", // Dark Red
    moderate: "#EA580C", // Orange
    minor: "#64748B", // Gray
  },

  fuel: {
    available: "#059669", // Emerald
    unavailable: "#94A3B8", // Gray-Blue
  },

  truckRestrictions: {
    weight: "#9333EA", // Purple
    height: "#7C3AED", // Violet
    noTrucks: "#5B21B6", // Deep Purple
    other: "#64748B", // Gray
  },

  restAreas: {
    complete: "#D97706", // Amber
    parking: "#B45309", // Dark Amber
    stop: "#92400E", // Darker Amber
  },
}

/**
 * Marker size configurations
 * Based on priority and zoom level
 */
export const markerSizes = {
  traffic: {
    severe: 24,
    moderate: 20,
    minor: 16,
  },
  fuel: 18,
  restrictions: 20,
  restAreas: 22,
}
