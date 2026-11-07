import type { ColumnDef } from "@tanstack/react-table"
import { Check, Copy, Trash2 } from "lucide-react"

import type { VehiclePublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import { cn } from "@/lib/utils"

function CopyId({ id }: { id: string }) {
  const [copiedText, copy] = useCopyToClipboard()
  const isCopied = copiedText === id

  return (
    <div className="flex items-center gap-1.5 group">
      <span className="font-mono text-xs text-muted-foreground" title={id}>
        {id.slice(0, 8)}
      </span>
      <Button
        variant="ghost"
        size="icon"
        className="size-6 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={() => copy(id)}
      >
        {isCopied ? (
          <Check className="size-3 text-green-500" />
        ) : (
          <Copy className="size-3" />
        )}
        <span className="sr-only">Copy ID</span>
      </Button>
    </div>
  )
}

const statusVariant: Record<
  VehiclePublic["status"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  active: "default",
  inactive: "secondary",
  maintenance: "destructive",
}

export function getColumns({
  selectedIds,
  allSelected,
  onToggleOne,
  onToggleAll,
  onDelete,
  canDelete,
}: {
  selectedIds: Set<string>
  allSelected: boolean
  onToggleOne: (id: string, checked: boolean) => void
  onToggleAll: (checked: boolean) => void
  onDelete: (vehicle: VehiclePublic) => void
  canDelete: boolean
}): ColumnDef<VehiclePublic>[] {
  if (!canDelete) {
    return baseColumns
  }
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
            aria-label="Delete vehicle"
            onClick={() => onDelete(row.original)}
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      ),
    },
  ]
}

const baseColumns: ColumnDef<VehiclePublic>[] = [
  {
    accessorKey: "id",
    header: "ID",
    cell: ({ row }) => <CopyId id={row.original.id} />,
  },
  {
    accessorKey: "unit_number",
    header: "Unit #",
    cell: ({ row }) => (
      <span className="font-mono text-sm font-medium">
        {row.original.unit_number}
      </span>
    ),
  },
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    accessorKey: "vehicle_type",
    header: "Type",
    cell: ({ row }) => (
      <span className="capitalize">{row.original.vehicle_type}</span>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge
        variant={statusVariant[row.original.status]}
        className="capitalize"
      >
        {row.original.status}
      </Badge>
    ),
  },
  {
    id: "vehicle_info",
    header: "Make / Model / Year",
    cell: ({ row }) => {
      const { make, model, year } = row.original
      const parts = [make, model, year].filter(Boolean)
      return (
        <span
          className={cn(
            "text-muted-foreground",
            parts.length === 0 && "italic",
          )}
        >
          {parts.length > 0 ? parts.join(" ") : "Not specified"}
        </span>
      )
    },
  },
  {
    id: "fuel",
    header: "Fuel",
    cell: ({ row }) => {
      const vehicle = row.original
      return (
        <span className="font-mono text-xs text-muted-foreground">
          {Number(vehicle.tank_capacity_gallons)} gal tank ·{" "}
          {Number(vehicle.consumption_mpg)} mpg
        </span>
      )
    },
  },
]
