/**
 * LayerTogglePanel component
 *
 * Provides UI controls to show/hide individual map layers
 */

import { Eye, EyeOff } from "lucide-react"
import { useCallback, useState } from "react"

export type LayerType =
  | "route"
  | "traffic"
  | "fuel"
  | "truck-restrictions"
  | "rest-areas"

interface LayerConfig {
  id: LayerType
  label: string
  icon: string // Unicode symbol or emoji
  description: string
  badge?: string | number
}

interface LayerTogglePanelProps {
  visibleLayers: Set<LayerType>
  onToggleLayer: (layer: LayerType) => void
  counts?: Partial<Record<LayerType, number>>
}

const LAYER_CONFIGS: LayerConfig[] = [
  {
    id: "route",
    label: "Route",
    icon: "━━",
    description: "Your calculated route",
  },
  {
    id: "traffic",
    label: "Traffic",
    icon: "▲",
    description: "Road incidents and congestion",
    badge: undefined, // Will be set from props
  },
  {
    id: "fuel",
    label: "Fuel Stations",
    icon: "💧",
    description: "Available fuel stations",
    badge: undefined,
  },
  {
    id: "truck-restrictions",
    label: "Truck Restrictions",
    icon: "⬣",
    description: "Weight limits, no-truck zones",
    badge: undefined,
  },
  {
    id: "rest-areas",
    label: "Rest Areas",
    icon: "▢",
    description: "Truck stops and rest areas",
    badge: undefined,
  },
]

export function LayerTogglePanel({
  visibleLayers,
  onToggleLayer,
  counts = {},
}: LayerTogglePanelProps) {
  const [isExpanded, setIsExpanded] = useState(true)

  const handleToggle = useCallback(
    (layer: LayerType) => {
      onToggleLayer(layer)
    },
    [onToggleLayer],
  )

  return (
    <div
      className="absolute top-4 right-4 bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden z-10"
      style={{ maxWidth: "320px" }}
    >
      {/* Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
        aria-controls="map-layers-panel"
        className="w-full flex items-center justify-between px-4 py-3 bg-gradient-to-r from-gray-50 to-white hover:from-gray-100 hover:to-gray-50 transition-colors border-b border-gray-200"
      >
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Map Layers</h3>
          <p className="text-xs text-gray-500">Show/hide layers</p>
        </div>
        <svg
          aria-hidden="true"
          focusable="false"
          className={`w-5 h-5 text-gray-600 transition-transform ${
            isExpanded ? "transform rotate-180" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <title>
            {isExpanded ? "Collapse layer panel" : "Expand layer panel"}
          </title>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 14l-7 7m0 0l-7-7m7 7V3"
          />
        </svg>
      </button>

      {/* Layers List */}
      {isExpanded && (
        <div
          id="map-layers-panel"
          className="px-2 py-2 space-y-1 max-h-96 overflow-y-auto"
        >
          {LAYER_CONFIGS.map((config) => {
            const isVisible = visibleLayers.has(config.id)
            const count = counts[config.id]

            return (
              <button
                type="button"
                key={config.id}
                onClick={() => handleToggle(config.id)}
                aria-pressed={isVisible}
                aria-label={`${isVisible ? "Hide" : "Show"} ${config.label} layer`}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-md transition-all ${
                  isVisible
                    ? "bg-blue-50 border border-blue-200"
                    : "bg-gray-50 border border-gray-200"
                }`}
              >
                <div className="flex items-center gap-2 flex-1 text-left">
                  {/* Shape indicator */}
                  <div className="text-xl flex-shrink-0">{config.icon}</div>

                  {/* Layer info */}
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-gray-900 truncate">
                      {config.label}
                    </div>
                    <div className="text-xs text-gray-500 truncate">
                      {config.description}
                    </div>
                  </div>

                  {/* Badge */}
                  {count !== undefined && count > 0 && (
                    <span className="text-xs font-semibold text-gray-700 bg-gray-200 px-2 py-1 rounded flex-shrink-0">
                      {count}
                    </span>
                  )}
                </div>

                {/* Toggle icon */}
                <div className="flex-shrink-0 ml-2">
                  {isVisible ? (
                    <Eye className="w-4 h-4 text-blue-600" />
                  ) : (
                    <EyeOff className="w-4 h-4 text-gray-400" />
                  )}
                </div>
              </button>
            )
          })}
        </div>
      )}

      {/* Footer hint */}
      {isExpanded && (
        <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 text-xs text-gray-600">
          Click to toggle layer visibility
        </div>
      )}
    </div>
  )
}
