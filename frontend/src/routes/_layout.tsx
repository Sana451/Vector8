import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"

import { Footer } from "@/components/Common/Footer"
import { Logo } from "@/components/Common/Logo"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      })
    }
  },
})

function Layout() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="bg-transparent">
        <header className="sticky top-0 z-10 flex h-18 shrink-0 items-center justify-between gap-3 border-b border-border/70 bg-[color:rgba(251,250,245,0.78)] px-4 backdrop-blur md:px-6 dark:bg-[color:rgba(16,20,26,0.78)]">
          <div className="flex items-center gap-3">
            <SidebarTrigger className="-ml-1 text-muted-foreground" />
            <div className="hidden h-8 w-px bg-border/80 md:block" />
            <div className="hidden md:block">
              <p className="vector8-kicker">Operations workspace</p>
              <p className="text-sm font-semibold tracking-tight">
                Vector8 control panel
              </p>
            </div>
          </div>
          <Logo variant="icon" className="md:hidden" />
        </header>
        <main className="flex-1 p-4 md:p-8">
          <div className="mx-auto flex max-w-7xl flex-col gap-6">
            <Outlet />
          </div>
        </main>
        <Footer />
      </SidebarInset>
    </SidebarProvider>
  )
}
