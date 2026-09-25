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
  const [isExpanded, setIsExpanded] = useState(false)

  const handleToggle = useCallback(
    (layer: LayerType) => {
      onToggleLayer(layer)
    },
    [onToggleLayer],
  )

  return (
    <div
      className="absolute top-4 right-4 bg-white dark:bg-slate-950 rounded-lg shadow-md border border-border/70 dark:border-border overflow-hidden z-10"
      style={{ maxWidth: "320px" }}
    >
      {/* Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
        aria-controls="map-layers-panel"
        className="w-full flex items-center justify-between px-4 py-3 bg-gradient-to-r from-gray-50/50 to-transparent dark:from-slate-900/50 dark:to-transparent hover:from-gray-100/50 dark:hover:from-slate-800/50 hover:to-transparent dark:hover:to-transparent transition-colors border-b border-border/40 dark:border-border/60"
      >
        <div>
          <h3 className="text-sm font-semibold text-foreground dark:text-slate-50">
            Map Layers
          </h3>
          <p className="text-xs text-muted-foreground dark:text-slate-400">
            Show/hide layers
          </p>
        </div>
        <svg
          aria-hidden="true"
          focusable="false"
          className={`w-5 h-5 text-muted-foreground dark:text-slate-400 transition-transform ${
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
                    ? "bg-primary/10 dark:bg-primary/20 border border-primary/30 dark:border-primary/40"
                    : "bg-muted/40 dark:bg-slate-800/60 border border-border/50 dark:border-slate-700/60"
                }`}
              >
                <div className="flex items-center gap-2 flex-1 text-left">
                  {/* Shape indicator */}
                  <div className="text-xl flex-shrink-0 dark:drop-shadow-sm">
                    {config.icon}
                  </div>

                  {/* Layer info */}
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-foreground dark:text-slate-50 truncate">
                      {config.label}
                    </div>
                    <div className="text-xs text-muted-foreground dark:text-slate-400 truncate">
                      {config.description}
                    </div>
                  </div>

                  {/* Badge */}
                  {count !== undefined && count > 0 && (
                    <span className="text-xs font-semibold text-foreground dark:text-slate-50 bg-muted/80 dark:bg-slate-700/80 px-2 py-1 rounded flex-shrink-0">
                      {count}
                    </span>
                  )}
                </div>

                {/* Toggle icon */}
                <div className="flex-shrink-0 ml-2">
                  {isVisible ? (
                    <Eye className="w-4 h-4 text-primary dark:text-primary" />
                  ) : (
                    <EyeOff className="w-4 h-4 text-muted-foreground dark:text-slate-500" />
                  )}
                </div>
              </button>
            )
          })}
        </div>
      )}

      {/* Footer hint */}
      {isExpanded && (
        <div className="px-4 py-2 bg-muted/30 dark:bg-slate-800/50 border-t border-border/40 dark:border-slate-700/60 text-xs text-muted-foreground dark:text-slate-400">
          Click to toggle layer visibility
        </div>
      )}
    </div>
  )
}
