import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-[5px] font-semibold transition-all disabled:pointer-events-none disabled:opacity-35 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 [&_svg]:shrink-0 outline-none focus-visible:ring-[3px] focus-visible:ring-[color:rgba(217,142,43,0.22)] aria-invalid:ring-[color:rgba(156,59,46,0.16)]",
  {
    variants: {
      variant: {
        default:
          "border border-transparent bg-[var(--amber-500)] text-[var(--ink-900)] shadow-none hover:bg-[#c47d24]",
        destructive:
          "border border-transparent bg-[var(--danger)] text-[var(--paper-50)] hover:opacity-95",
        outline:
          "border-[1.5px] border-[var(--border)] bg-transparent text-foreground hover:border-[var(--foreground)] hover:bg-[color:rgba(217,142,43,0.08)]",
        secondary:
          "border border-transparent bg-[var(--ink-900)] text-[var(--paper-50)] hover:bg-[#332a1c] dark:bg-[var(--slate-700)] dark:text-[var(--slate-text)]",
        ghost:
          "border border-transparent bg-transparent text-foreground hover:bg-[color:rgba(217,142,43,0.08)]",
        link: "px-0 text-[var(--teal-700)] underline-offset-4 hover:underline",
      },
      size: {
        default: "min-h-10 px-[17px] py-[9px] text-[13px] has-[>svg]:px-[15px]",
        sm: "min-h-8 gap-1.5 px-3 py-1.5 text-[11.5px] has-[>svg]:px-2.5",
        lg: "min-h-11 px-[22px] py-3 text-[14px] has-[>svg]:px-5",
        icon: "size-9",
        "icon-sm": "size-8",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot : "button"

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
