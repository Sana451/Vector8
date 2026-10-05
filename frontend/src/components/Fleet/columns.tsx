import type { ColumnDef } from "@tanstack/react-table"
import { Check, Copy } from "lucide-react"

import type { VehiclePublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import { cn } from "@/lib/utils"
import { VehicleActionsMenu } from "./VehicleActionsMenu"

function CopyId({ id }: { id: string }) {
  const [copiedText, copy] = useCopyToClipboard()
  const isCopied = copiedText === id

  return (
    <div className="flex items-center gap-1.5 group">
      <span className="font-mono text-xs text-muted-foreground">{id}</span>
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

export const columns: ColumnDef<VehiclePublic>[] = [
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
    id: "fuel_profile",
    header: "Fuel Profile",
    cell: ({ row }) => {
      const profile = row.original.fuel_profile
      return (
        <span className="font-mono text-xs text-muted-foreground">
          {profile.tank_capacity_gallons} gal tank · {profile.consumption_mpg}{" "}
          mpg
        </span>
      )
    },
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <VehicleActionsMenu vehicle={row.original} />
      </div>
    ),
  },
]
