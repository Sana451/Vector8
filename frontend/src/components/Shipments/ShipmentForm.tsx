import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, Plus, Trash2 } from "lucide-react"
import { useFieldArray, useForm } from "react-hook-form"
import { z } from "zod"

import {
  type ShipmentDetailPublic,
  ShipmentsService,
  type ShipmentUpdateRequest,
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
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const LOW_CONFIDENCE = 0.8

const stopSchema = z.object({
  kind: z.enum(["pickup", "dropoff"]),
  company_name: z.string(),
  address_raw: z.string().min(1, { message: "Address is required" }),
  scheduled_at_start: z.string(),
  scheduled_at_end: z.string(),
  reference_number: z.string(),
  contact_name: z.string(),
  contact_phone: z.string(),
  notes: z.string(),
})

const formSchema = z.object({
  broker_name: z.string(),
  broker_contact: z.string(),
  reference_number: z.string(),
  total_weight_lbs: z
    .string()
    .refine((value) => value === "" || !Number.isNaN(Number(value)), {
      message: "Must be a number",
    }),
  rate_total: z
    .string()
    .refine((value) => value === "" || !Number.isNaN(Number(value)), {
      message: "Must be a number",
    }),
  rate_currency: z.string(),
  equipment_type: z.string(),
  notes: z.string(),
  stops: z.array(stopSchema).min(1, { message: "At least one stop" }),
})

type FormValues = z.infer<typeof formSchema>

/**
 * Documents carry local wall-clock times, which the backend stores as UTC.
 * Both conversions therefore use UTC parts so a round-trip never shifts a
 * schedule by the reviewer's own timezone.
 */
function toDateTimeInput(value?: string | null) {
  if (!value) return ""
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ""
  return parsed.toISOString().slice(0, 16)
}

function fromDateTimeInput(value: string) {
  return value ? `${value}:00Z` : null
}

function emptyToNull(value: string) {
  return value.trim() === "" ? null : value.trim()
}

function LowConfidenceHint({ score }: { score: number | undefined }) {
  if (score === undefined || score >= LOW_CONFIDENCE) {
    return null
  }
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <AlertTriangle className="size-3.5 text-amber-500" />
      </TooltipTrigger>
      <TooltipContent>
        The parser was {Math.round(score * 100)}% sure. Check the original.
      </TooltipContent>
    </Tooltip>
  )
}

export default function ShipmentForm({
  shipment,
}: {
  shipment: ShipmentDetailPublic
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const confidence = (shipment.field_confidence ?? {}) as Record<string, number>

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: {
      broker_name: shipment.broker_name ?? "",
      broker_contact: shipment.broker_contact ?? "",
      reference_number: shipment.reference_number ?? "",
      total_weight_lbs: shipment.total_weight_lbs ?? "",
      rate_total: shipment.rate_total ?? "",
      rate_currency: shipment.rate_currency ?? "USD",
      equipment_type: shipment.equipment_type ?? "",
      notes: shipment.notes ?? "",
      stops: (shipment.stops ?? []).map((stop) => ({
        kind: stop.kind,
        company_name: stop.company_name ?? "",
        address_raw: stop.address_raw,
        scheduled_at_start: toDateTimeInput(stop.scheduled_at_start),
        scheduled_at_end: toDateTimeInput(stop.scheduled_at_end),
        reference_number: stop.reference_number ?? "",
        contact_name: stop.contact_name ?? "",
        contact_phone: stop.contact_phone ?? "",
        notes: stop.notes ?? "",
      })),
    },
  })

  const stops = useFieldArray({ control: form.control, name: "stops" })

  const mutation = useMutation({
    mutationFn: async (body: ShipmentUpdateRequest) =>
      (
        await ShipmentsService.updateShipment({
          path: { shipment_id: shipment.id },
          body,
        })
      ).data,
    onSuccess: () => {
      showSuccessToast("Shipment updated.")
      queryClient.invalidateQueries({ queryKey: ["shipments"] })
      queryClient.invalidateQueries({ queryKey: ["shipment", shipment.id] })
    },
    onError: (error: Error) => {
      handleError.call(showErrorToast, error)
    },
  })

  const onSubmit = (values: FormValues) => {
    mutation.mutate({
      broker_name: emptyToNull(values.broker_name),
      broker_contact: emptyToNull(values.broker_contact),
      reference_number: emptyToNull(values.reference_number),
      total_weight_lbs: emptyToNull(values.total_weight_lbs),
      rate_total: emptyToNull(values.rate_total),
      rate_currency: emptyToNull(values.rate_currency),
      equipment_type: emptyToNull(values.equipment_type),
      notes: emptyToNull(values.notes),
      stops: values.stops.map((stop) => ({
        kind: stop.kind,
        company_name: emptyToNull(stop.company_name),
        address_raw: stop.address_raw.trim(),
        scheduled_at_start: fromDateTimeInput(stop.scheduled_at_start),
        scheduled_at_end: fromDateTimeInput(stop.scheduled_at_end),
        reference_number: emptyToNull(stop.reference_number),
        contact_name: emptyToNull(stop.contact_name),
        contact_phone: emptyToNull(stop.contact_phone),
        notes: emptyToNull(stop.notes),
      })),
    })
  }

  const textField = (
    name: keyof Omit<FormValues, "stops">,
    label: string,
    confidenceKey?: string,
  ) => (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel className="flex items-center gap-1.5">
            {label}
            <LowConfidenceHint score={confidence[confidenceKey ?? name]} />
          </FormLabel>
          <FormControl>
            <Input {...field} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <section className="vector8-surface space-y-4 p-4">
          <h2 className="text-base font-semibold">Load</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {textField("reference_number", "Load number")}
            {textField("broker_name", "Broker")}
            {textField("broker_contact", "Broker contact")}
            {textField("equipment_type", "Equipment")}
            {textField("total_weight_lbs", "Weight (lbs)")}
            {textField("rate_total", "Rate")}
            {textField("rate_currency", "Currency")}
            {textField("notes", "Notes")}
          </div>
        </section>

        <section className="vector8-surface space-y-4 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">Stops</h2>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                stops.append({
                  kind: "dropoff",
                  company_name: "",
                  address_raw: "",
                  scheduled_at_start: "",
                  scheduled_at_end: "",
                  reference_number: "",
                  contact_name: "",
                  contact_phone: "",
                  notes: "",
                })
              }
            >
              <Plus className="size-4" />
              Add stop
            </Button>
          </div>

          {stops.fields.map((stopField, index) => (
            <div
              key={stopField.id}
              className="space-y-4 rounded-lg border border-[var(--slate-border)] p-4"
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-muted-foreground">
                  Stop {index + 1}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={index === 0}
                    onClick={() => stops.move(index, index - 1)}
                  >
                    Up
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={index === stops.fields.length - 1}
                    onClick={() => stops.move(index, index + 1)}
                  >
                    Down
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => stops.remove(index)}
                  >
                    <Trash2 className="size-4" />
                    <span className="sr-only">Remove stop</span>
                  </Button>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name={`stops.${index}.kind`}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Kind</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        value={field.value}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="pickup">Pickup</SelectItem>
                          <SelectItem value="dropoff">Dropoff</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name={`stops.${index}.company_name`}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Company</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name={`stops.${index}.address_raw`}
                  render={({ field }) => (
                    <FormItem className="sm:col-span-2">
                      <FormLabel>Address</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name={`stops.${index}.scheduled_at_start`}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Window start (UTC)</FormLabel>
                      <FormControl>
                        <Input type="datetime-local" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name={`stops.${index}.scheduled_at_end`}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Window end (UTC)</FormLabel>
                      <FormControl>
                        <Input type="datetime-local" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name={`stops.${index}.reference_number`}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Reference</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name={`stops.${index}.contact_name`}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Contact</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name={`stops.${index}.contact_phone`}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Phone</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name={`stops.${index}.notes`}
                  render={({ field }) => (
                    <FormItem className="sm:col-span-2">
                      <FormLabel>Notes</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {shipment.stops?.[index]?.geocode_error ? (
                <p className="text-sm text-amber-500">
                  Address could not be geocoded:{" "}
                  {shipment.stops[index].geocode_error}
                </p>
              ) : null}
            </div>
          ))}
        </section>

        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => form.reset()}
            disabled={mutation.isPending}
          >
            Reset
          </Button>
          <LoadingButton type="submit" loading={mutation.isPending}>
            Save corrections
          </LoadingButton>
        </div>
      </form>
    </Form>
  )
}
