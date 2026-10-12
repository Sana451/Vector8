import type { Map as MapLibreMap } from "maplibre-gl"
import { useCallback, useMemo } from "react"
import { buildMeasureFeatures } from "@/lib/measure"
import type { Coordinate } from "@/lib/routing"
import { type LayerWithVisibility, useGeoJsonLayer } from "./useGeoJsonLayer"

interface MeasureLayerProps {
  mapInstance: MapLibreMap | null
  points: Coordinate[]
  showVertices: boolean
}

export function MeasureLayer({
  mapInstance,
  points,
  showVertices,
}: MeasureLayerProps) {
  const data = useMemo(
    () => buildMeasureFeatures(points, showVertices),
    [points, showVertices],
  )

  const buildLayers = useCallback(
    (sourceId: string): LayerWithVisibility[] =>
      [
        {
          id: "measure-line",
          type: "line",
          source: sourceId,
          filter: ["==", ["get", "kind"], "line"],
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": "#e11d48",
            "line-width": 3,
            "line-dasharray": [2, 1],
          },
        },
        {
          id: "measure-vertices",
          type: "circle",
          source: sourceId,
          filter: ["==", ["get", "kind"], "vertex"],
          paint: {
            "circle-radius": 5,
            "circle-color": "#ffffff",
            "circle-stroke-color": "#e11d48",
            "circle-stroke-width": 2,
          },
        },
      ] as LayerWithVisibility[],
    [],
  )

  useGeoJsonLayer({ mapInstance, sourceId: "measure", buildLayers, data })

  return null
}
