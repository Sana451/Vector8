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
    <svg width="28" height="36" viewBox="0 0 28 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M14 2C8.477 2 4 6.477 4 12c0 8.413 8.294 17.205 9.241 18.175a1 1 0 0 0 1.518 0C15.706 29.205 24 20.413 24 12 24 6.477 19.523 2 14 2Z"
        fill="${color}"
        stroke="white"
        stroke-width="1.75"
        stroke-linejoin="round"
      />
      <path
        d="M10.5 8.5A1.5 1.5 0 0 1 12 7h4a1.5 1.5 0 0 1 1.5 1.5v8A1.5 1.5 0 0 1 16 18h-4a1.5 1.5 0 0 1-1.5-1.5v-8Z"
        fill="white"
      />
      <path
        d="M17.5 10.5h1.25A1.75 1.75 0 0 1 20.5 12.25V18a1 1 0 0 1-1 1h-0.75"
        stroke="white"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <path
        d="M12.25 10.25h3.5v3h-3.5z"
        fill="${color}"
        opacity="0.25"
      />
      <path
        d="M11.75 20h5"
        stroke="white"
        stroke-width="1.5"
        stroke-linecap="round"
      />
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
    available: "#10B981", // Bright Emerald Green
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
