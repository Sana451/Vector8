import type { ColumnDef } from "@tanstack/react-table"
import { AlertTriangle, PencilLine, Trash2 } from "lucide-react"

import type { ShipmentPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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

const baseColumns: ColumnDef<ShipmentPublic>[] = [
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
  onDelete: (shipment: ShipmentPublic) => void
}): ColumnDef<ShipmentPublic>[] {
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
