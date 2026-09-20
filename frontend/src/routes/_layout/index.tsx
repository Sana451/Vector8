import { createFileRoute } from "@tanstack/react-router"

import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Dashboard - Vector8",
      },
    ],
  }),
})

function Dashboard() {
  const { user: currentUser } = useAuth()
  const displayName = currentUser?.full_name || currentUser?.email || "Operator"

  return (
    <div className="flex flex-col gap-6">
      <section className="vector8-page-header space-y-4">
        <div className="space-y-2">
          <p className="vector8-kicker">Control tower</p>
          <h1 className="max-w-3xl text-3xl font-semibold tracking-tight md:text-4xl">
            Welcome back, {displayName}.
          </h1>
          <p className="max-w-2xl text-base leading-7 text-muted-foreground">
            Your Vector8 workspace is ready for routing, fleet operations and
            admin workflows.
          </p>
        </div>
        <div className="vector8-grid-stats">
          <div className="stat-card">
            <div className="k">Workspace</div>
            <div className="v">Vector8</div>
          </div>
          <div className="stat-card">
            <div className="k">Role</div>
            <div className="v">
              {currentUser?.is_superuser ? "Admin" : "Member"}
            </div>
          </div>
          <div className="stat-card">
            <div className="k">Auth status</div>
            <div className="v pos">Active</div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.3fr_0.9fr]">
        <div className="vector8-surface p-6">
          <p className="vector8-kicker">Operational focus</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">
            The interface now follows the Vector8 toolkit.
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground">
            Warm paper surfaces highlight content, while dark chrome keeps
            navigation stable and out of the way for dispatch-heavy flows.
          </p>
          <div className="mt-6 list-card">
            <div className="row-item">
              <div>
                <div className="t">Routes and maps</div>
                <div className="d">
                  Use the map module for network visibility.
                </div>
              </div>
              <span className="badge badge-teal">Ready</span>
            </div>
            <div className="row-item">
              <div>
                <div className="t">Items & resources</div>
                <div className="d">
                  Manage active entities from a calmer data table UI.
                </div>
              </div>
              <span className="badge badge-amber">Updated</span>
            </div>
            <div className="row-item">
              <div>
                <div className="t">Admin controls</div>
                <div className="d">
                  Review users, permissions and account settings.
                </div>
              </div>
              <span className="badge badge-outline">Secure</span>
            </div>
          </div>
        </div>

        <div className="vector8-surface p-6">
          <p className="vector8-kicker">Session</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">
            Signed in as {displayName}
          </h2>
          <div className="mt-5 space-y-4 text-sm leading-7 text-muted-foreground">
            <p>
              Use the sidebar to move between dashboard, items and admin tools.
            </p>
            <p>
              The updated theme keeps operational data clear on both light and
              dark surfaces.
            </p>
          </div>
          <div className="mt-6 rounded-2xl border border-border/80 bg-background/80 p-4">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
              Account email
            </p>
            <p className="mt-2 break-all text-sm font-medium text-foreground">
              {currentUser?.email}
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
