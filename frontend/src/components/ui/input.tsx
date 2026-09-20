import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "w-full min-w-0 rounded-[5px] border-[1.5px] border-[var(--border)] bg-[var(--input)] px-3 py-2.5 text-[13.5px] text-foreground shadow-none transition-[border-color,box-shadow,background-color] outline-none placeholder:text-muted-foreground/80 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 file:border-0 file:bg-transparent file:font-medium file:text-foreground",
        "focus-visible:border-[var(--amber-500)] focus-visible:ring-[3px] focus-visible:ring-[color:rgba(217,142,43,0.16)]",
        "aria-invalid:border-[var(--danger)] aria-invalid:ring-[color:rgba(156,59,46,0.16)]",
        className
      )}
      {...props}
    />
  )
}

export { Input }
