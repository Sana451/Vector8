import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"

export function useRowSelection(ids: string[]) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const selected = ids.filter((id) => selectedIds.has(id))
  const allSelected = ids.length > 0 && selected.length === ids.length

  const toggleOne = (id: string, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  const toggleAll = (checked: boolean) => {
    setSelectedIds(checked ? new Set(ids) : new Set())
  }

  const clear = () => setSelectedIds(new Set())

  return { selectedIds, selected, allSelected, toggleOne, toggleAll, clear }
}

export function SelectionBar({
  count,
  onDelete,
}: {
  count: number
  onDelete: () => void
}) {
  if (count === 0) return null
  return (
    <div className="vector8-surface flex items-center justify-between gap-3 px-4 py-2">
      <span className="text-sm">Selected: {count}</span>
      <Button variant="destructive" size="sm" onClick={onDelete}>
        <Trash2 className="mr-2 h-4 w-4" />
        Delete selected
      </Button>
    </div>
  )
}

export function BulkDeleteDialog({
  ids,
  noun,
  queryKey,
  deleteOne,
  onClose,
  onDeleted,
}: {
  ids: string[]
  noun: string
  queryKey: string
  deleteOne: (id: string) => Promise<unknown>
  onClose: () => void
  onDeleted: () => void
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: async (targetIds: string[]) => {
      const results = await Promise.allSettled(targetIds.map(deleteOne))
      const failed = results.filter((r) => r.status === "rejected").length
      return { total: targetIds.length, failed }
    },
    onSuccess: ({ total, failed }) => {
      if (failed === 0) {
        showSuccessToast(
          total === 1
            ? `${capitalize(noun)} deleted`
            : `Deleted ${total} ${noun}s`,
        )
      } else {
        showErrorToast(
          `Deleted ${total - failed} of ${total}, ${failed} failed`,
        )
      }
      onDeleted()
      onClose()
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: [queryKey] })
    },
  })

  const count = ids.length

  return (
    <Dialog open={count > 0} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {count === 1 ? `Delete ${noun}?` : `Delete ${count} ${noun}s?`}
          </DialogTitle>
          <DialogDescription>
            {count === 1
              ? `This ${noun} will be permanently deleted. This action cannot be undone.`
              : `${count} selected ${noun}s will be permanently deleted. This action cannot be undone.`}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2">
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            variant="destructive"
            loading={mutation.isPending}
            onClick={() => mutation.mutate(ids)}
          >
            Delete
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}
