import type { ColumnDef } from "@tanstack/react-table"
import { AlertTriangle, PencilLine, Trash2 } from "lucide-react"

import type { ShipmentListItemPublic, ShipmentStopPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const planningVariant: Record<
  ShipmentListItemPublic["planning_status"],
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

function formatWindow(start?: string | null, end?: string | null) {
  if (!start && !end) return "—"
  const fmt = (value: string) =>
    new Date(value).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  if (start && end) return `${fmt(start)} – ${fmt(end)}`
  return fmt((start ?? end) as string)
}

function StopCell({ stop }: { stop?: ShipmentStopPublic | null }) {
  if (!stop) return <span className="text-muted-foreground">—</span>
  const address = stop.geocoded_address ?? stop.address_raw ?? "—"
  return (
    <div className="flex flex-col">
      <span className="text-sm">{address}</span>
      <span className="text-xs text-muted-foreground">
        {formatWindow(stop.scheduled_at_start, stop.scheduled_at_end)}
      </span>
    </div>
  )
}

const baseColumns: ColumnDef<ShipmentListItemPublic>[] = [
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
    id: "from",
    header: "From",
    cell: ({ row }) => <StopCell stop={row.original.first_pickup} />,
  },
  {
    id: "to",
    header: "To",
    cell: ({ row }) => <StopCell stop={row.original.last_dropoff} />,
  },
]

export function getColumns({
  selectedIds,
  allSelected,
  onToggleOne,
  onToggleAll,
  onDelete,
}: {
  selectedIds: Set<string>
  allSelected: boolean
  onToggleOne: (id: string, checked: boolean) => void
  onToggleAll: (checked: boolean) => void
  onDelete: (shipment: ShipmentListItemPublic) => void
}): ColumnDef<ShipmentListItemPublic>[] {
  return [
    {
      id: "select",
      header: () => (
        <Checkbox
          checked={allSelected}
          onCheckedChange={(value) => onToggleAll(value === true)}
          aria-label="Select all"
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={selectedIds.has(row.original.id)}
          onCheckedChange={(value) =>
            onToggleOne(row.original.id, value === true)
          }
          aria-label="Select row"
        />
      ),
    },
    ...baseColumns,
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Delete shipment"
            onClick={() => onDelete(row.original)}
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      ),
    },
  ]
}
