import * as React from "react"
import { Eye, EyeOff } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "./button"

interface PasswordInputProps extends React.ComponentProps<"input"> {
  error?: string
}

const PasswordInput = React.forwardRef<HTMLInputElement, PasswordInputProps>(
  ({ className, error, ...props }, ref) => {
    const [showPassword, setShowPassword] = React.useState(false)

    return (
      <div className="relative">
        <input
          type={showPassword ? "text" : "password"}
          data-slot="input"
          className={cn(
            "w-full min-w-0 rounded-[5px] border-[1.5px] border-[var(--border)] bg-[var(--input)] px-3 py-2.5 pr-11 text-[13.5px] text-foreground shadow-none transition-[border-color,box-shadow,background-color] outline-none placeholder:text-muted-foreground/80 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 file:border-0 file:bg-transparent file:font-medium file:text-foreground",
            "focus-visible:border-[var(--amber-500)] focus-visible:ring-[3px] focus-visible:ring-[color:rgba(217,142,43,0.16)]",
            "aria-invalid:border-[var(--danger)] aria-invalid:ring-[color:rgba(156,59,46,0.16)]",
            className
          )}
          ref={ref}
          aria-invalid={!!error}
          {...props}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="absolute right-1 top-1/2 h-8 w-8 -translate-y-1/2 rounded-md px-0 py-0 hover:bg-[color:rgba(217,142,43,0.08)]"
          onClick={() => setShowPassword(!showPassword)}
          aria-label={showPassword ? "Hide password" : "Show password"}
        >
          {showPassword ? (
            <EyeOff className="h-4 w-4 text-muted-foreground" />
          ) : (
            <Eye className="h-4 w-4 text-muted-foreground" />
          )}
        </Button>
      </div>
    )
  }
)

PasswordInput.displayName = "PasswordInput"

export { PasswordInput }
