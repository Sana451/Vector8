/**
 * New vehicle page. Superuser only, matching the backend POST endpoint.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query"
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

export const Route = createFileRoute("/_layout/fleet_/new")({
  component: NewVehicle,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({ to: "/fleet" })
    }
  },
  head: () => ({
    meta: [{ title: "New vehicle - Vector8" }],
  }),
})

function NewVehicle() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (data: ReturnType<typeof toVehiclePayload>) =>
      VehiclesService.createVehicle({ body: data }),
    onSuccess: () => {
      showSuccessToast("Vehicle created successfully")
      navigate({ to: "/fleet" })
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
          <Link to="/fleet">
            <ArrowLeft className="size-4" />
            Back to fleet
          </Link>
        </Button>
        <div className="vector8-page-header flex flex-col gap-2">
          <p className="vector8-kicker">Vehicle</p>
          <h1 className="text-3xl font-semibold tracking-tight">Add vehicle</h1>
          <p className="text-muted-foreground">
            Fill in the details to add a new vehicle to the fleet.
          </p>
        </div>
      </div>

      <VehicleForm
        defaultValues={vehicleFormDefaults()}
        submitLabel="Save"
        isPending={mutation.isPending}
        showCopySource
        onSubmit={(data) => mutation.mutate(toVehiclePayload(data))}
        onCancel={() => navigate({ to: "/fleet" })}
      />
    </div>
  )
}
