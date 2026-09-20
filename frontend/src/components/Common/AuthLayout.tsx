import { Appearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="vector8-auth-shell grid min-h-svh lg:grid-cols-[1.15fr_0.85fr]">
      <div className="vector8-auth-aside relative hidden overflow-hidden lg:flex lg:flex-col lg:justify-between lg:p-10">
        <div className="space-y-8">
          <Logo variant="full" className="h-10" asLink={false} />
          <div className="max-w-xl space-y-5">
            <p className="vector8-kicker text-[var(--slate-text-dim)]">
              Fleet intelligence platform
            </p>
            <h1 className="text-4xl font-semibold leading-tight text-[var(--slate-text)] xl:text-5xl">
              Operate routes, assets and customer delivery flows from one
              Vector8 workspace.
            </h1>
            <p className="max-w-lg text-base leading-7 text-[var(--slate-text-dim)]">
              The new interface follows the Vector8 UI toolkit — warm surfaces,
              sharp operational contrast and clear actions for dispatch teams.
            </p>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-3">
          <div className="vector8-auth-feature">
            <p className="vector8-kicker text-[var(--slate-text-faint)]">
              Routing
            </p>
            <p className="mt-2 text-sm leading-6 text-[var(--slate-text)]">
              Keep maps, traffic and route decisions in one operational surface.
            </p>
          </div>
          <div className="vector8-auth-feature">
            <p className="vector8-kicker text-[var(--slate-text-faint)]">
              Assets
            </p>
            <p className="mt-2 text-sm leading-6 text-[var(--slate-text)]">
              Track items, users and permissions with a calmer, more readable
              UI.
            </p>
          </div>
          <div className="vector8-auth-feature">
            <p className="vector8-kicker text-[var(--slate-text-faint)]">
              Reliability
            </p>
            <p className="mt-2 text-sm leading-6 text-[var(--slate-text)]">
              Clear status language, stronger hierarchy and fewer distractions.
            </p>
          </div>
        </div>
      </div>

      <div className="flex min-h-svh flex-col gap-6 p-4 sm:p-6 lg:p-8">
        <div className="flex items-center justify-between gap-4">
          <Logo variant="full" className="h-8 lg:hidden" asLink={false} />
          <Appearance />
        </div>

        <div className="flex flex-1 items-center justify-center">
          <div className="vector8-auth-card w-full max-w-md">{children}</div>
        </div>

        <Footer />
      </div>
    </div>
  )
}
