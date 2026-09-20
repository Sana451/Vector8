import { Link } from "@tanstack/react-router"

import { useTheme } from "@/components/theme-provider"
import { cn } from "@/lib/utils"
import iconAmber from "/assets/images/vector8-icon-amber.svg"
import iconDark from "/assets/images/vector8-icon-dark.svg"
import logoDark from "/assets/images/vector8-lockup-dark.svg"
import logoLight from "/assets/images/vector8-lockup-light.svg"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme === "dark"

  const fullLogo = isDark ? logoLight : logoDark
  const iconLogo = isDark ? iconAmber : iconDark

  const content =
    variant === "responsive" ? (
      <>
        <img
          src={fullLogo}
          alt="Vector8"
          className={cn(
            "h-7 w-auto group-data-[collapsible=icon]:hidden",
            className,
          )}
        />
        <img
          src={iconLogo}
          alt="Vector8"
          className={cn(
            "hidden size-6 group-data-[collapsible=icon]:block",
            className,
          )}
        />
      </>
    ) : (
      <img
        src={variant === "full" ? fullLogo : iconLogo}
        alt="Vector8"
        className={cn(variant === "full" ? "h-7 w-auto" : "size-6", className)}
      />
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
