import type { ColumnDef } from "@tanstack/react-table"
import { AlertTriangle, PencilLine } from "lucide-react"

import type { ShipmentPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const planningVariant: Record<
  ShipmentPublic["planning_status"],
  "default" | "secondary" | "outline"
> = {
  unplanned: "secondary",
  planned: "default",
  completed: "outline",
  archived: "outline",
}

/**
 * Below this, the parser was unsure enough that a human should look.
 */
const REVIEW_THRESHOLD = 0.8

function formatMoney(amount?: string | null, currency?: string | null) {
  if (!amount) return "—"
  const value = Number(amount)
  if (Number.isNaN(value)) return amount
  return `${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${currency ?? ""}`.trim()
}

function formatWeight(weight?: string | null) {
  if (!weight) return "—"
  const value = Number(weight)
  if (Number.isNaN(value)) return weight
  return `${value.toLocaleString()} lbs`
}

export const columns: ColumnDef<ShipmentPublic>[] = [
  {
    accessorKey: "reference_number",
    header: "Load #",
    cell: ({ row }) => (
      <span className="font-mono text-sm font-medium">
        {row.original.reference_number ?? "—"}
      </span>
    ),
  },
  {
    accessorKey: "broker_name",
    header: "Broker",
    cell: ({ row }) => row.original.broker_name ?? "—",
  },
  {
    accessorKey: "rate_total",
    header: "Rate",
    cell: ({ row }) =>
      formatMoney(row.original.rate_total, row.original.rate_currency),
  },
  {
    accessorKey: "total_weight_lbs",
    header: "Weight",
    cell: ({ row }) => formatWeight(row.original.total_weight_lbs),
  },
  {
    accessorKey: "planning_status",
    header: "Planning",
    cell: ({ row }) => (
      <Badge variant={planningVariant[row.original.planning_status]}>
        {row.original.planning_status}
      </Badge>
    ),
  },
  {
    id: "quality",
    header: "Extraction",
    cell: ({ row }) => {
      const confidence = Number(row.original.extraction_confidence ?? 0)
      const needsReview = confidence < REVIEW_THRESHOLD

      return (
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">
            {row.original.extraction_confidence
              ? `${Math.round(confidence * 100)}%`
              : "—"}
          </span>
          {needsReview ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <AlertTriangle className="size-4 text-amber-500" />
              </TooltipTrigger>
              <TooltipContent>
                The parser was unsure. Check this one against the original.
              </TooltipContent>
            </Tooltip>
          ) : null}
          {row.original.is_manually_edited ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <PencilLine className="size-4 text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>Edited by hand</TooltipContent>
            </Tooltip>
          ) : null}
        </div>
      )
    },
  },
  {
    accessorKey: "created_at",
    header: "Uploaded",
    cell: ({ row }) => new Date(row.original.created_at).toLocaleString(),
  },
]
