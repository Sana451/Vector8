import { Briefcase, Home, Users } from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [
  { icon: Home, title: "Dashboard", path: "/" },
  { icon: Briefcase, title: "Items", path: "/items" },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()

  const items = currentUser?.is_superuser
    ? [...baseItems, { icon: Users, title: "Admin", path: "/admin" }]
    : baseItems

  return (
    <Sidebar collapsible="icon" variant="inset" className="border-r-0">
      <SidebarHeader className="px-3 py-4 group-data-[collapsible=icon]:px-2">
        <div className="rounded-2xl border border-[var(--slate-border)] bg-[linear-gradient(180deg,rgba(236,230,214,0.06),rgba(236,230,214,0.02))] p-4 group-data-[collapsible=icon]:p-2">
          <Logo variant="responsive" />
          <div className="mt-4 space-y-1 group-data-[collapsible=icon]:hidden">
            <p className="vector8-kicker text-[var(--slate-text-faint)]">
              Dispatch shell
            </p>
            <p className="text-sm leading-6 text-[var(--slate-text-dim)]">
              Routes, items and admin tools arranged for daily operations.
            </p>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent className="px-1">
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter className="gap-3 px-3 pb-4">
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
