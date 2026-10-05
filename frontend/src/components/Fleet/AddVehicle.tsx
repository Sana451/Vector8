import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type VehicleCreate, VehiclesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

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
    routing_profile_id: z.string().optional(),
    fuel_profile_name: z
      .string()
      .min(1, { message: "Fuel profile name is required" }),
    tank_capacity_gallons: numericString("Tank capacity is required"),
    usable_tank_capacity_gallons: numericString(
      "Usable tank capacity is required",
    ),
    consumption_mpg: numericString("Consumption is required"),
    reserve_gallons: numericString("Reserve is required"),
    min_refuel_gallons: z.string().optional(),
    max_refuel_gallons: z.string().optional(),
  })
  .refine(
    (data) =>
      !data.year || (Number(data.year) >= 1900 && Number(data.year) <= 3000),
    { message: "Year must be between 1900 and 3000", path: ["year"] },
  )

type FormData = z.infer<typeof formSchema>

const AddVehicle = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: "",
      unit_number: "",
      status: "active",
      vehicle_type: "truck",
      make: "",
      model: "",
      year: "",
      routing_profile_id: "",
      fuel_profile_name: "",
      tank_capacity_gallons: "",
      usable_tank_capacity_gallons: "",
      consumption_mpg: "",
      reserve_gallons: "",
      min_refuel_gallons: "",
      max_refuel_gallons: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: VehicleCreate) =>
      VehiclesService.createVehicle({ body: data }),
    onSuccess: () => {
      showSuccessToast("Vehicle created successfully")
      form.reset()
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["vehicles"] })
    },
  })

  const onSubmit = (data: FormData) => {
    const payload: VehicleCreate = {
      name: data.name,
      unit_number: data.unit_number,
      status: data.status,
      vehicle_type: data.vehicle_type,
      make: data.make || undefined,
      model: data.model || undefined,
      year: data.year ? Number(data.year) : undefined,
      routing_profile_id: data.routing_profile_id || undefined,
      fuel_profile: {
        name: data.fuel_profile_name,
        tank_capacity_gallons: data.tank_capacity_gallons,
        usable_tank_capacity_gallons: data.usable_tank_capacity_gallons,
        consumption_mpg: data.consumption_mpg,
        reserve_gallons: data.reserve_gallons,
        min_refuel_gallons: data.min_refuel_gallons || undefined,
        max_refuel_gallons: data.max_refuel_gallons || undefined,
      },
    }
    mutation.mutate(payload)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="my-4">
          <Plus className="mr-2" />
          Add Vehicle
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add Vehicle</DialogTitle>
          <DialogDescription>
            Fill in the details to add a new vehicle to the fleet.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
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
              </div>

              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="vehicle_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Vehicle Type <span className="text-destructive">*</span>
                      </FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                      >
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
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select status" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="active">Active</SelectItem>
                          <SelectItem value="inactive">Inactive</SelectItem>
                          <SelectItem value="maintenance">
                            Maintenance
                          </SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
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

              <FormField
                control={form.control}
                name="routing_profile_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Routing Profile ID</FormLabel>
                    <FormControl>
                      <Input placeholder="UUID (optional)" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="border-t pt-4">
                <h4 className="mb-3 text-sm font-semibold">Fuel Profile</h4>
                <div className="grid gap-4">
                  <FormField
                    control={form.control}
                    name="fuel_profile_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          Profile Name{" "}
                          <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input placeholder="Standard Diesel" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <div className="grid grid-cols-2 gap-4">
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
                    <FormField
                      control={form.control}
                      name="usable_tank_capacity_gallons"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>
                            Usable Capacity (gal){" "}
                            <span className="text-destructive">*</span>
                          </FormLabel>
                          <FormControl>
                            <Input placeholder="145" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
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
                    <FormField
                      control={form.control}
                      name="reserve_gallons"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>
                            Reserve (gal){" "}
                            <span className="text-destructive">*</span>
                          </FormLabel>
                          <FormControl>
                            <Input placeholder="20" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="min_refuel_gallons"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Min Refuel (gal)</FormLabel>
                          <FormControl>
                            <Input placeholder="Optional" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="max_refuel_gallons"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Max Refuel (gal)</FormLabel>
                          <FormControl>
                            <Input placeholder="Optional" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </div>
              </div>
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Save
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddVehicle
