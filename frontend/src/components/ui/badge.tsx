import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-[3px] px-[9px] py-1 font-mono text-[10.5px] font-semibold whitespace-nowrap [&>svg]:pointer-events-none [&>svg]:size-3 focus-visible:ring-[3px] focus-visible:ring-[color:rgba(217,142,43,0.18)] transition-[color,box-shadow,border-color,background-color]",
  {
    variants: {
      variant: {
        default:
          "border border-transparent bg-[var(--amber-500)] text-[var(--ink-900)] [a&]:hover:bg-[#c47d24]",
        secondary:
          "border border-transparent bg-[var(--teal-500)] text-white [a&]:hover:bg-[var(--teal-700)]",
        destructive:
          "border border-transparent bg-[var(--danger-bg)] text-[var(--danger)] [a&]:hover:bg-[color:rgba(156,59,46,0.18)]",
        outline:
          "border border-[var(--border)] bg-transparent text-muted-foreground [a&]:hover:bg-[color:rgba(217,142,43,0.08)] [a&]:hover:text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant,
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "span"

  return (
    <Comp
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
