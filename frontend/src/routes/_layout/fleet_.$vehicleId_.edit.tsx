/**
 * Vehicle edit page. Superusers and dispatchers, matching the backend PATCH endpoint.
 */

import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import {
  createFileRoute,
  Link,
  redirect,
  useNavigate,
} from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"

import { UsersService, VehiclesService } from "@/client"
import {
  toVehiclePayload,
  VehicleForm,
  vehicleFormDefaults,
} from "@/components/Fleet/VehicleForm"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/fleet_/$vehicleId_/edit")({
  component: EditVehicle,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (!user.is_superuser && user.role !== "dispatcher") {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({
    meta: [{ title: "Edit vehicle - Vector8" }],
  }),
})

function EditVehicle() {
  const { vehicleId } = Route.useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: vehicle } = useSuspenseQuery({
    queryKey: ["vehicles", vehicleId],
    queryFn: async () =>
      (await VehiclesService.getVehicle({ path: { vehicle_id: vehicleId } }))
        .data,
  })

  const mutation = useMutation({
    mutationFn: (data: ReturnType<typeof toVehiclePayload>) =>
      VehiclesService.updateVehicle({
        path: { vehicle_id: vehicleId },
        body: data,
      }),
    onSuccess: () => {
      showSuccessToast("Vehicle updated successfully")
      navigate({ to: "/fleet/$vehicleId", params: { vehicleId } })
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["vehicles"] })
    },
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        <Button variant="ghost" size="sm" className="w-fit" asChild>
          <Link to="/fleet/$vehicleId" params={{ vehicleId }}>
            <ArrowLeft className="size-4" />
            Back to vehicle
          </Link>
        </Button>
        <div className="vector8-page-header flex flex-col gap-2">
          <p className="vector8-kicker">Vehicle</p>
          <h1 className="text-3xl font-semibold tracking-tight">
            Edit {vehicle.unit_number} · {vehicle.name}
          </h1>
          <p className="font-mono text-xs text-muted-foreground">
            ID: {vehicle.id}
          </p>
        </div>
      </div>

      <VehicleForm
        defaultValues={vehicleFormDefaults(vehicle)}
        submitLabel="Save"
        isPending={mutation.isPending}
        onSubmit={(data) => mutation.mutate(toVehiclePayload(data))}
        onCancel={() =>
          navigate({ to: "/fleet/$vehicleId", params: { vehicleId } })
        }
      />
    </div>
  )
}
