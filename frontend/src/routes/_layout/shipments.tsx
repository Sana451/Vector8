import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router"
import { FileText } from "lucide-react"
import { Suspense } from "react"

import { ShipmentsService, UsersService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { columns } from "@/components/Shipments/columns"
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

function ShipmentsTableContent() {
  const navigate = useNavigate()
  const { data: shipments } = useSuspenseQuery(getShipmentsQueryOptions())
  const shipmentList = shipments?.data ?? []

  if (shipmentList.length === 0) {
    return (
      <div className="vector8-surface flex flex-col items-center justify-center py-12 text-center">
        <div className="mb-4 rounded-full bg-[color:rgba(217,142,43,0.08)] p-4">
          <FileText className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No shipments yet</h3>
        <p className="text-muted-foreground">
          Upload a rate confirmation to turn it into a plannable shipment.
        </p>
      </div>
    )
  }

  return (
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
  )
}

function Shipments() {
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
      <Suspense fallback={<PendingShipments />}>
        <ShipmentsTableContent />
      </Suspense>
    </div>
  )
}
