import type { UserRole } from "@/client"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export const USER_ROLE_LABELS: Record<UserRole, string> = {
  admin: "Admin",
  dispatcher: "Dispatcher",
  driver: "Driver",
}

interface RoleSelectProps {
  value: UserRole | undefined
  onChange: (role: UserRole) => void
}

export function RoleSelect({ value, onChange }: RoleSelectProps) {
  return (
    <Select value={value} onValueChange={(role) => onChange(role as UserRole)}>
      <SelectTrigger>
        <SelectValue placeholder="Select a role" />
      </SelectTrigger>
      <SelectContent>
        {(Object.keys(USER_ROLE_LABELS) as UserRole[]).map((role) => (
          <SelectItem key={role} value={role}>
            {USER_ROLE_LABELS[role]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
