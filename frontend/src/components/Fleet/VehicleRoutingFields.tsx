import { CircleHelp } from "lucide-react"
import { useState } from "react"
import { useFormContext } from "react-hook-form"
import { z } from "zod"
import type { VehiclePublic } from "@/client"
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ROUTING_FIELD_HELP } from "./routingFieldHelp"

const HelpHint = ({ text }: { text: string }) => {
  const [open, setOpen] = useState(false)
  return (
    <Tooltip
      open={open}
      onOpenChange={(next) => {
        if (!next) setOpen(false)
      }}
    >
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="Show help"
          className="text-muted-foreground hover:text-foreground"
          onPointerDown={(e) => e.preventDefault()}
          onClick={(e) => {
            e.preventDefault()
            setOpen((value) => !value)
          }}
        >
          <CircleHelp className="size-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs text-left">{text}</TooltipContent>
    </Tooltip>
  )
}

const optionalInt = (min: number, max: number) =>
  z
    .string()
    .optional()
    .refine(
      (value) =>
        !value ||
        (Number.isInteger(Number(value)) &&
          Number(value) >= min &&
          Number(value) <= max),
      { message: `Whole number ${min}–${max}` },
    )

export const routingFieldsShape = {
  height_in: optionalInt(1, 1968),
  width_in: optionalInt(1, 1968),
  length_in: optionalInt(1, 11811),
  gross_weight_lbs: optionalInt(1, 2000000),
  weight_per_axle_lbs: optionalInt(1, 2000000),
  axle_count: optionalInt(2, 255),
  tires_count: optionalInt(1, 255),
  trailer_count: optionalInt(0, 255),
  trailer_length_in: optionalInt(1, 787),
  kpra_length_in: optionalInt(1, 11811),
  payload_capacity_lbs: optionalInt(1, 2000000),
  max_speed_mph: optionalInt(1, 156),
}

export type RoutingFormValues = {
  [K in keyof typeof routingFieldsShape]?: string
}

type RoutingKey = keyof typeof routingFieldsShape

const routingKeys = Object.keys(routingFieldsShape) as RoutingKey[]

const toText = (value: number | null | undefined) =>
  value === null || value === undefined ? "" : String(value)

export const routingDefaults = (
  vehicle?: VehiclePublic,
): Required<RoutingFormValues> => {
  const result = {} as Required<RoutingFormValues>
  for (const key of routingKeys) {
    result[key] = key === "trailer_count" ? "0" : toText(vehicle?.[key])
  }
  return result
}

export const routingPayload = (data: RoutingFormValues) => {
  const result: Partial<Record<RoutingKey, number | null>> & {
    trailer_count: number
  } = { trailer_count: data.trailer_count ? Number(data.trailer_count) : 0 }
  for (const key of routingKeys) {
    if (key === "trailer_count") continue
    const value = data[key]
    result[key] = value ? Number(value) : null
  }
  return result
}

const FIELDS: { name: RoutingKey; label: string; placeholder: string }[] = [
  { name: "height_in", label: "Height (in)", placeholder: "150" },
  { name: "width_in", label: "Width (in)", placeholder: "96" },
  { name: "length_in", label: "Length (in)", placeholder: "312" },
  {
    name: "gross_weight_lbs",
    label: "Gross weight (lb)",
    placeholder: "26000",
  },
  {
    name: "weight_per_axle_lbs",
    label: "Weight per axle (lb)",
    placeholder: "13000",
  },
  {
    name: "payload_capacity_lbs",
    label: "Payload capacity (lb)",
    placeholder: "8300",
  },
  { name: "axle_count", label: "Axle count", placeholder: "2" },
  { name: "tires_count", label: "Tires count", placeholder: "6" },
  { name: "max_speed_mph", label: "Max speed (mph)", placeholder: "65" },
  { name: "trailer_count", label: "Trailer count", placeholder: "0" },
  { name: "trailer_length_in", label: "Trailer length (in)", placeholder: "" },
  { name: "kpra_length_in", label: "KPRA length (in)", placeholder: "" },
]

export const VehicleRoutingFields = () => {
  const { control } = useFormContext<RoutingFormValues>()
  return (
    <div className="border-t pt-4">
      <h4 className="mb-1 text-sm font-semibold">Routing constraints</h4>
      <p className="mb-3 text-xs text-muted-foreground">
        Optional. Used to avoid roads the vehicle cannot legally use. Trailer
        length and KPRA length apply only when trailer count is at least 1.
      </p>
      <div className="grid grid-cols-3 gap-4">
        {FIELDS.map(({ name, label, placeholder }) => (
          <FormField
            key={name}
            control={control}
            name={name}
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  {label}
                  <HelpHint text={ROUTING_FIELD_HELP[name]} />
                </FormLabel>
                <FormControl>
                  <Input
                    type="number"
                    placeholder={placeholder}
                    {...field}
                    value={field.value ?? ""}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        ))}
      </div>
    </div>
  )
}
