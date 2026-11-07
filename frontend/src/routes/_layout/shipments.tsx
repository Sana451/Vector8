import { useQuery } from "@tanstack/react-query"
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router"
import { FileText } from "lucide-react"
import { useState } from "react"

import {
  type ShipmentListItemPublic,
  ShipmentsService,
  UsersService,
} from "@/client"
import {
  BulkDeleteDialog,
  SelectionBar,
  useRowSelection,
} from "@/components/Common/BulkDelete"
import { DataTable } from "@/components/Common/DataTable"
import { getColumns } from "@/components/Shipments/columns"
import UploadShipment from "@/components/Shipments/UploadShipment"
import { Skeleton } from "@/components/ui/skeleton"

function getShipmentsQueryOptions() {
  return {
    queryFn: async () =>
      (await ShipmentsService.listShipments({ query: { skip: 0, limit: 100 } }))
        .data,
    queryKey: ["shipments"],
  }
}

export const Route = createFileRoute("/_layout/shipments")({
  component: Shipments,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (user.role === "driver") {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Shipments - Vector8",
      },
    ],
  }),
})

function PendingShipments() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, index) => (
        <Skeleton key={`shipment-row-${index}`} className="h-12 w-full" />
      ))}
    </div>
  )
}

function Shipments() {
  const navigate = useNavigate()
  const { data: shipments, isLoading } = useQuery(getShipmentsQueryOptions())
  const shipmentList = shipments?.data ?? []
  const ids = shipmentList.map((s) => s.id)
  const selection = useRowSelection(ids)
  const [pendingIds, setPendingIds] = useState<string[]>([])

  const columns = getColumns({
    selectedIds: selection.selectedIds,
    allSelected: selection.allSelected,
    onToggleOne: selection.toggleOne,
    onToggleAll: selection.toggleAll,
    onDelete: (shipment: ShipmentListItemPublic) =>
      setPendingIds([shipment.id]),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="vector8-page-header flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-2">
          <p className="vector8-kicker">Load intake</p>
          <h1 className="text-3xl font-semibold tracking-tight">Shipments</h1>
          <p className="text-muted-foreground">
            Upload rate confirmations, review what was extracted and plan them
            onto a vehicle.
          </p>
        </div>
        <UploadShipment />
      </div>
      {isLoading ? <PendingShipments /> : null}
      {!isLoading && shipmentList.length === 0 ? (
        <div className="vector8-surface flex flex-col items-center justify-center py-12 text-center">
          <div className="mb-4 rounded-full bg-[color:rgba(217,142,43,0.08)] p-4">
            <FileText className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold">No shipments yet</h3>
          <p className="text-muted-foreground">
            Upload a rate confirmation to turn it into a plannable shipment.
          </p>
        </div>
      ) : null}
      {!isLoading && shipmentList.length > 0 ? (
        <div className="space-y-3">
          <SelectionBar
            count={selection.selected.length}
            onDelete={() => setPendingIds(selection.selected)}
          />
          <DataTable
            columns={columns}
            data={shipmentList}
            onRowClick={(shipment) =>
              navigate({
                to: "/shipments/$shipmentId",
                params: { shipmentId: shipment.id },
              })
            }
          />
          <BulkDeleteDialog
            ids={pendingIds}
            noun="shipment"
            queryKey="shipments"
            deleteOne={(id) =>
              ShipmentsService.deleteShipment({ path: { shipment_id: id } })
            }
            onClose={() => setPendingIds([])}
            onDeleted={selection.clear}
          />
        </div>
      ) : null}
    </div>
  )
}
