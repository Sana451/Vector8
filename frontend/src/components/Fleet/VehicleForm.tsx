import { zodResolver } from "@hookform/resolvers/zod"
import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  type VehicleCreate,
  type VehiclePublic,
  VehiclesService,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  routingDefaults,
  routingFieldsShape,
  routingPayload,
  VehicleRoutingFields,
} from "./VehicleRoutingFields"

const numericString = (message: string) =>
  z
    .string()
    .min(1, { message })
    .refine((value) => !Number.isNaN(Number(value)), {
      message: "Must be a number",
    })

const formSchema = z
  .object({
    name: z.string().min(1, { message: "Name is required" }),
    unit_number: z.string().min(1, { message: "Unit number is required" }),
    status: z.enum(["active", "inactive", "maintenance"]),
    vehicle_type: z.enum(["tractor", "truck"]),
    make: z.string().optional(),
    model: z.string().optional(),
    year: z.string().optional(),
    ...routingFieldsShape,
    tank_capacity_gallons: numericString("Tank capacity is required"),
    consumption_mpg: numericString("Consumption is required"),
  })
  .refine(
    (data) =>
      !data.year || (Number(data.year) >= 1900 && Number(data.year) <= 3000),
    { message: "Year must be between 1900 and 3000", path: ["year"] },
  )

export type VehicleFormData = z.infer<typeof formSchema>

export function vehicleFormDefaults(vehicle?: VehiclePublic): VehicleFormData {
  if (!vehicle) {
    return {
      name: "",
      unit_number: "",
      status: "active",
      vehicle_type: "truck",
      make: "",
      model: "",
      year: "",
      ...routingDefaults(),
      tank_capacity_gallons: "",
      consumption_mpg: "",
    }
  }
  return {
    name: vehicle.name,
    unit_number: vehicle.unit_number,
    status: vehicle.status,
    vehicle_type: vehicle.vehicle_type,
    make: vehicle.make ?? "",
    model: vehicle.model ?? "",
    year: vehicle.year ? String(vehicle.year) : "",
    ...routingDefaults(vehicle),
    tank_capacity_gallons: String(vehicle.tank_capacity_gallons),
    consumption_mpg: String(vehicle.consumption_mpg),
  }
}

export function toVehiclePayload(data: VehicleFormData): VehicleCreate {
  return {
    name: data.name,
    unit_number: data.unit_number,
    status: data.status,
    vehicle_type: data.vehicle_type,
    make: data.make || undefined,
    model: data.model || undefined,
    year: data.year ? Number(data.year) : undefined,
    ...routingPayload(data),
    tank_capacity_gallons: data.tank_capacity_gallons,
    consumption_mpg: data.consumption_mpg,
  }
}

interface VehicleFormProps {
  defaultValues: VehicleFormData
  submitLabel: string
  isPending: boolean
  showCopySource?: boolean
  onSubmit: (data: VehicleFormData) => void
  onCancel: () => void
}

export function VehicleForm({
  defaultValues,
  submitLabel,
  isPending,
  showCopySource = false,
  onSubmit,
  onCancel,
}: VehicleFormProps) {
  const [sourceVehicleId, setSourceVehicleId] = useState("")

  const form = useForm<VehicleFormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues,
  })

  const { data: vehiclesResponse } = useQuery({
    queryKey: ["vehicles"],
    queryFn: async () =>
      (await VehiclesService.listVehicles({ query: { skip: 0, limit: 100 } }))
        .data,
    enabled: showCopySource,
  })
  const vehicles = vehiclesResponse?.data ?? []

  const handleCopyVehicle = (vehicleId: string) => {
    setSourceVehicleId(vehicleId)
    const source = vehicles.find((vehicle) => vehicle.id === vehicleId)
    if (!source) return
    form.reset({
      ...vehicleFormDefaults(source),
      unit_number: "",
    })
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="vector8-surface flex flex-col gap-6 p-4 sm:p-5"
      >
        {showCopySource && vehicles.length > 0 && (
          <div className="grid gap-2">
            <Label>Copy from existing vehicle</Label>
            <Select
              value={sourceVehicleId || undefined}
              onValueChange={handleCopyVehicle}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a vehicle to copy (optional)" />
              </SelectTrigger>
              <SelectContent>
                {vehicles.map((vehicle) => (
                  <SelectItem key={vehicle.id} value={vehicle.id}>
                    {vehicle.name} ({vehicle.unit_number})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              All fields are copied except the unit number, which must be
              unique.
            </p>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  Name <span className="text-destructive">*</span>
                </FormLabel>
                <FormControl>
                  <Input placeholder="Freightliner 150" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="unit_number"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  Unit Number <span className="text-destructive">*</span>
                </FormLabel>
                <FormControl>
                  <Input placeholder="UNIT-001" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="vehicle_type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  Vehicle Type <span className="text-destructive">*</span>
                </FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="truck">Truck</SelectItem>
                    <SelectItem value="tractor">Tractor</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="status"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Status</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select status" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                    <SelectItem value="maintenance">Maintenance</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <FormField
            control={form.control}
            name="make"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Make</FormLabel>
                <FormControl>
                  <Input placeholder="Freightliner" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="model"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Model</FormLabel>
                <FormControl>
                  <Input placeholder="Cascadia" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="year"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Year</FormLabel>
                <FormControl>
                  <Input placeholder="2022" type="number" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <VehicleRoutingFields />

        <div className="border-t pt-4">
          <h4 className="mb-3 text-sm font-semibold">Fuel</h4>
          <div className="grid gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="tank_capacity_gallons"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Tank Capacity (gal){" "}
                      <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="150" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div>
                <div className="text-sm font-medium leading-none">
                  Usable Capacity (gal)
                </div>
                <div className="rounded-md border border-input bg-muted px-3 py-2 text-sm text-muted-foreground">
                  {form.watch("tank_capacity_gallons")
                    ? (
                        Number(form.watch("tank_capacity_gallons")) * 0.95
                      ).toFixed(2)
                    : "0.00"}{" "}
                  (95% auto-calculated)
                </div>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="consumption_mpg"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Consumption (MPG){" "}
                      <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="6.8" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t pt-4">
          <Button
            variant="outline"
            type="button"
            onClick={onCancel}
            disabled={isPending}
          >
            Cancel
          </Button>
          <LoadingButton type="submit" loading={isPending}>
            {submitLabel}
          </LoadingButton>
        </div>
      </form>
    </Form>
  )
}
