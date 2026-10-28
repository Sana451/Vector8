/**
 * TripActions component
 *
 * Everything a driver needs to take a saved trip out of the browser: file
 * downloads for a truck GPS and deep links that open the route in a phone
 * navigator.
 */

import { Download, ExternalLink, Loader2 } from "lucide-react"
import { useState } from "react"

import { downloadTripPlanExport } from "@/api/tripPlans"
import type { TripPlanDetailPublic, TripPlanExportFormat } from "@/client"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import {
  buildGoogleMapsLegs,
  buildHereWeGoUrl,
  type NavigatorPoint,
} from "@/lib/navigatorLinks"
import { handleError } from "@/utils"

const EXPORT_FORMATS: { format: TripPlanExportFormat; label: string }[] = [
  { format: "gpx", label: "GPX" },
  { format: "kml", label: "KML" },
  { format: "csv", label: "CSV" },
]

function fileName(trip: TripPlanDetailPublic): string {
  const stem = trip.name.replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-|-$/g, "")
  return stem || "trip"
}

/** The API already frames the stops with the start and destination points. */
function navigatorPoints(trip: TripPlanDetailPublic): NavigatorPoint[] {
  return (trip.stops ?? []).map((stop) => ({
    label: stop.label,
    coordinate: stop.coordinate as [number, number],
  }))
}

export function TripActions({ trip }: { trip: TripPlanDetailPublic }) {
  const { showErrorToast } = useCustomToast()
  const [downloading, setDownloading] = useState<TripPlanExportFormat | null>(
    null,
  )

  const points = navigatorPoints(trip)
  const legs = buildGoogleMapsLegs(points)
  const hereUrl = buildHereWeGoUrl(points)

  const download = async (format: TripPlanExportFormat) => {
    setDownloading(format)
    try {
      await downloadTripPlanExport(trip.id, format, fileName(trip))
    } catch (err) {
      handleError.call(showErrorToast, err as Error)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="vector8-surface flex flex-col gap-4 p-4">
      <div className="flex flex-col gap-2">
        <p className="vector8-kicker">Download</p>
        <div className="flex flex-wrap gap-2">
          {EXPORT_FORMATS.map(({ format, label }) => (
            <Button
              key={format}
              variant="outline"
              disabled={downloading !== null}
              onClick={() => download(format)}
            >
              {downloading === format ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              {label}
            </Button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          GPX and KML carry the verified route and every stop; CSV lists the
          stops for paperwork.
        </p>
      </div>

      {legs.length > 0 ? (
        <div className="flex flex-col gap-2">
          <p className="vector8-kicker">Open in a navigator</p>
          <div className="flex flex-wrap gap-2">
            {legs.map((leg) => (
              <Button key={leg.url} variant="outline" asChild>
                <a href={leg.url} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="h-4 w-4" />
                  {legs.length === 1
                    ? "Google Maps"
                    : `Google Maps · leg ${leg.index}`}
                </a>
              </Button>
            ))}
            {hereUrl ? (
              <Button variant="outline" asChild>
                <a href={hereUrl} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="h-4 w-4" />
                  HERE WeGo
                </a>
              </Button>
            ) : null}
          </div>
          {legs.length > 1 ? (
            <p className="text-xs text-muted-foreground">
              Google Maps limits waypoints per link, so the trip is split into{" "}
              {legs.length} legs — drive them in order.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
