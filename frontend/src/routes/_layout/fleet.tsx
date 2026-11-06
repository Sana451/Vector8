import { useQuery } from "@tanstack/react-query"
import {
  createFileRoute,
  Link,
  redirect,
  useNavigate,
} from "@tanstack/react-router"
import { Plus, Truck } from "lucide-react"
import { useState } from "react"

import { UsersService, type VehiclePublic, VehiclesService } from "@/client"
import {
  BulkDeleteDialog,
  SelectionBar,
  useRowSelection,
} from "@/components/Common/BulkDelete"
import { DataTable } from "@/components/Common/DataTable"
import { getColumns } from "@/components/Fleet/columns"
import PendingVehicles from "@/components/Pending/PendingVehicles"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"

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
    if (!user.is_superuser && user.role !== "dispatcher") {
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

function Fleet() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canDelete = Boolean(user?.is_superuser)
  const { data: vehicles, isLoading } = useQuery(getVehiclesQueryOptions())
  const vehicleList = vehicles?.data ?? []
  const ids = vehicleList.map((v) => v.id)
  const selection = useRowSelection(ids)
  const [pendingIds, setPendingIds] = useState<string[]>([])

  const columns = getColumns({
    selectedIds: selection.selectedIds,
    allSelected: selection.allSelected,
    onToggleOne: selection.toggleOne,
    onToggleAll: selection.toggleAll,
    onDelete: (vehicle: VehiclePublic) => setPendingIds([vehicle.id]),
    canDelete,
  })

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
        {user?.is_superuser ? (
          <Button asChild>
            <Link to="/fleet/new">
              <Plus className="mr-2" />
              Add Vehicle
            </Link>
          </Button>
        ) : null}
      </div>
      {isLoading ? <PendingVehicles /> : null}
      {!isLoading && vehicleList.length === 0 ? (
        <div className="vector8-surface flex flex-col items-center justify-center py-12 text-center">
          <div className="mb-4 rounded-full bg-[color:rgba(217,142,43,0.08)] p-4">
            <Truck className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold">
            No vehicles in the fleet yet
          </h3>
          <p className="text-muted-foreground">
            Add a new vehicle to start managing your fleet in Vector8.
          </p>
        </div>
      ) : null}
      {!isLoading && vehicleList.length > 0 ? (
        <div className="space-y-3">
          {canDelete ? (
            <SelectionBar
              count={selection.selected.length}
              onDelete={() => setPendingIds(selection.selected)}
            />
          ) : null}
          <DataTable
            columns={columns}
            data={vehicleList}
            onRowClick={(vehicle) =>
              navigate({
                to: "/fleet/$vehicleId",
                params: { vehicleId: vehicle.id },
              })
            }
          />
          {canDelete ? (
            <BulkDeleteDialog
              ids={pendingIds}
              noun="vehicle"
              queryKey="vehicles"
              deleteOne={(id) =>
                VehiclesService.deleteVehicle({ path: { vehicle_id: id } })
              }
              onClose={() => setPendingIds([])}
              onDeleted={selection.clear}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
