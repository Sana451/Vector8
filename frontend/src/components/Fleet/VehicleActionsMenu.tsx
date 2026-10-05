import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { VehiclePublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteVehicle from "./DeleteVehicle"
import EditVehicle from "./EditVehicle"

interface VehicleActionsMenuProps {
  vehicle: VehiclePublic
}

export const VehicleActionsMenu = ({ vehicle }: VehicleActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditVehicle vehicle={vehicle} onSuccess={() => setOpen(false)} />
        <DeleteVehicle id={vehicle.id} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
