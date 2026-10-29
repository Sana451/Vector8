/**
 * Vehicle detail page.
 *
 * Shows every stored characteristic of a fleet vehicle. The trailing underscore
 * keeps this page out of the fleet list's layout.
 */

import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import type { ReactNode } from "react"

import { UsersService, type VehiclePublic, VehiclesService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

export const Route = createFileRoute("/_layout/fleet_/$vehicleId")({
  component: VehicleDetail,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({
    meta: [{ title: "Vehicle - Vector8" }],
  }),
})

const statusVariant: Record<
  VehiclePublic["status"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  active: "default",
  inactive: "secondary",
  maintenance: "destructive",
}

function display(value: string | number | null | undefined, unit?: string) {
  if (value === null || value === undefined || value === "") return "—"
  return unit ? `${value} ${unit}` : `${value}`
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="vector8-surface flex flex-col gap-4 p-4">
      <h2 className="text-base font-semibold">{title}</h2>
      <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{children}</dl>
    </section>
  )
}

function VehicleDetail() {
  const { vehicleId } = Route.useParams()
  const { data: vehicle } = useSuspenseQuery({
    queryKey: ["vehicle", vehicleId],
    queryFn: async () =>
      (await VehiclesService.getVehicle({ path: { vehicle_id: vehicleId } }))
        .data,
  })

  const title = `${vehicle.unit_number} · ${vehicle.name}`

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
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
            <Badge
              variant={statusVariant[vehicle.status]}
              className="capitalize"
            >
              {vehicle.status}
            </Badge>
          </div>
          <p className="font-mono text-xs text-muted-foreground">
            ID: {vehicle.id}
          </p>
        </div>
      </div>

      <Section title="General">
        <Field label="Unit #" value={vehicle.unit_number} />
        <Field label="Name" value={vehicle.name} />
        <Field
          label="Type"
          value={<span className="capitalize">{vehicle.vehicle_type}</span>}
        />
        <Field
          label="Status"
          value={<span className="capitalize">{vehicle.status}</span>}
        />
        <Field label="Make" value={display(vehicle.make)} />
        <Field label="Model" value={display(vehicle.model)} />
        <Field label="Year" value={display(vehicle.year)} />
      </Section>

      <Section title="Fuel">
        <Field
          label="Fuel type"
          value={<span className="capitalize">{vehicle.fuel_type}</span>}
        />
        <Field
          label="Tank capacity"
          value={display(Number(vehicle.tank_capacity_gallons), "gal")}
        />
        <Field
          label="Consumption"
          value={display(Number(vehicle.consumption_mpg), "mpg")}
        />
      </Section>

      <Section title="Dimensions">
        <Field label="Height" value={display(vehicle.height_in, "in")} />
        <Field label="Width" value={display(vehicle.width_in, "in")} />
        <Field label="Length" value={display(vehicle.length_in, "in")} />
        <Field
          label="KPRA length"
          value={display(vehicle.kpra_length_in, "in")}
        />
        <Field
          label="Trailer length"
          value={display(vehicle.trailer_length_in, "in")}
        />
        <Field label="Trailer count" value={display(vehicle.trailer_count)} />
      </Section>

      <Section title="Weight & load">
        <Field
          label="Gross weight"
          value={display(vehicle.gross_weight_lbs, "lbs")}
        />
        <Field
          label="Weight per axle"
          value={display(vehicle.weight_per_axle_lbs, "lbs")}
        />
        <Field
          label="Payload capacity"
          value={display(vehicle.payload_capacity_lbs, "lbs")}
        />
        <Field label="Axle count" value={display(vehicle.axle_count)} />
        <Field label="Tires count" value={display(vehicle.tires_count)} />
        <Field
          label="Max speed"
          value={display(vehicle.max_speed_mph, "mph")}
        />
      </Section>

      <div className="text-xs text-muted-foreground">
        Created {new Date(vehicle.created_at).toLocaleString()} · Updated{" "}
        {new Date(vehicle.updated_at).toLocaleString()}
      </div>
    </div>
  )
}
