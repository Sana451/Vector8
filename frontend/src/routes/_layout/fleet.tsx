import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Truck } from "lucide-react"
import { Suspense } from "react"

import { UsersService, VehiclesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import AddVehicle from "@/components/Fleet/AddVehicle"
import { columns } from "@/components/Fleet/columns"
import PendingVehicles from "@/components/Pending/PendingVehicles"

function getVehiclesQueryOptions() {
  return {
    queryFn: async () =>
      (await VehiclesService.listVehicles({ query: { skip: 0, limit: 100 } }))
        .data,
    queryKey: ["vehicles"],
  }
}

export const Route = createFileRoute("/_layout/fleet")({
  component: Fleet,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Fleet - Vector8",
      },
    ],
  }),
})

function FleetTableContent() {
  const { data: vehicles } = useSuspenseQuery(getVehiclesQueryOptions())
  const vehicleList = vehicles?.data ?? []

  if (vehicleList.length === 0) {
    return (
      <div className="vector8-surface flex flex-col items-center justify-center py-12 text-center">
        <div className="mb-4 rounded-full bg-[color:rgba(217,142,43,0.08)] p-4">
          <Truck className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No vehicles in the fleet yet</h3>
        <p className="text-muted-foreground">
          Add a new vehicle to start managing your fleet in Vector8.
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={vehicleList} />
}

function FleetTable() {
  return (
    <Suspense fallback={<PendingVehicles />}>
      <FleetTableContent />
    </Suspense>
  )
}

function Fleet() {
  return (
    <div className="flex flex-col gap-6">
      <div className="vector8-page-header flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-2">
          <p className="vector8-kicker">Fleet management</p>
          <h1 className="text-3xl font-semibold tracking-tight">Fleet</h1>
          <p className="text-muted-foreground">
            Add, review, update and remove vehicles in the Vector8 fleet.
          </p>
        </div>
        <AddVehicle />
      </div>
      <FleetTable />
    </div>
  )
}
