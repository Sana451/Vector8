/**
 * TripActions component
 *
 * Everything a driver needs to take a saved trip out of the browser: file
 * downloads for a truck GPS and deep links that open the route in a phone
 * navigator.
 */

import {
  AlertTriangle,
  ChevronDown,
  Download,
  ExternalLink,
  Loader2,
} from "lucide-react"
import { useState } from "react"

import { downloadTripPlanExport } from "@/api/tripPlans"
import type { TripPlanDetailPublic, TripPlanExportFormat } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
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

function openUrl(url: string) {
  window.open(url, "_blank", "noopener,noreferrer")
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
            {legs.length === 1 ? (
              <Button variant="outline" asChild>
                <a href={legs[0].url} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="h-4 w-4" />
                  Google Maps
                </a>
              </Button>
            ) : (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline">
                    <ExternalLink className="h-4 w-4" />
                    Google Maps
                    <ChevronDown className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="max-w-72">
                  <DropdownMenuLabel className="whitespace-normal font-normal text-xs text-muted-foreground">
                    Google Maps limits waypoints per link, so the trip is split
                    into {legs.length} legs — drive them in order.
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {legs.map((leg) => (
                    <DropdownMenuItem
                      key={leg.url}
                      onSelect={() => openUrl(leg.url)}
                    >
                      Leg {leg.index}
                    </DropdownMenuItem>
                  ))}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onSelect={() => {
                      for (const leg of legs) openUrl(leg.url)
                    }}
                  >
                    Open all legs
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
            {hereUrl ? (
              <Button variant="outline" asChild>
                <a href={hereUrl} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="h-4 w-4" />
                  HERE WeGo
                </a>
              </Button>
            ) : null}
          </div>
          <p className="flex items-start gap-2 text-xs text-red-600 dark:text-red-400">
            <AlertTriangle className="mt-px h-4 w-4 shrink-0" />
            <span>
              A navigator link does not carry the route built for your truck's
              dimensions: the navigator builds a route for a passenger car and
              only places the stops along it. To repeat the route exactly,{" "}
              <button
                type="button"
                className="underline underline-offset-2 hover:no-underline"
                disabled={downloading !== null}
                onClick={() => download("gpx")}
              >
                download the GPX
              </button>{" "}
              and open it in a dedicated app such as OsmAnd Maps or Organic
              Maps.
            </span>
          </p>
        </div>
      ) : null}
    </div>
  )
}
