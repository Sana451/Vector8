import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { FileUp, Upload } from "lucide-react"
import { useRef, useState } from "react"

import { ShipmentsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const MAX_DOCUMENT_BYTES = 20 * 1024 * 1024

export default function UploadShipment() {
  const [isOpen, setIsOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const reset = () => {
    setFile(null)
    setLocalError(null)
    if (inputRef.current) {
      inputRef.current.value = ""
    }
  }

  const mutation = useMutation({
    mutationFn: async (selected: File) =>
      (
        await ShipmentsService.uploadShipmentDocument({
          body: { file: selected },
        })
      ).data,
    onSuccess: (response) => {
      if (!response) {
        return
      }
      if (response.is_duplicate) {
        showSuccessToast(
          "This file was uploaded before — opening the existing shipment.",
        )
      } else {
        showSuccessToast("Document parsed. Review the extracted fields.")
      }
      setIsOpen(false)
      reset()
      queryClient.invalidateQueries({ queryKey: ["shipments"] })
      navigate({
        to: "/shipments/$shipmentId",
        params: { shipmentId: response.shipment.id },
      })
    },
    onError: (error: Error) => {
      handleError.call(showErrorToast, error)
    },
  })

  const handleSelect = (selected: File | null) => {
    setLocalError(null)
    if (!selected) {
      setFile(null)
      return
    }
    if (selected.size > MAX_DOCUMENT_BYTES) {
      setLocalError("The file is larger than 20 MB.")
      setFile(null)
      return
    }
    setFile(selected)
  }

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open)
        if (!open) {
          reset()
        }
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Upload className="size-4" />
          Upload document
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload rate confirmation</DialogTitle>
          <DialogDescription>
            Pick a PDF rate confirmation. Vector8 reads the pickup and delivery
            stops, the rate and the weight, then opens the shipment for review.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="shipment-document">PDF file</Label>
          <Input
            id="shipment-document"
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => handleSelect(event.target.files?.[0] ?? null)}
          />
          {file ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <FileUp className="size-4" />
              {file.name} ({Math.round(file.size / 1024)} KB)
            </p>
          ) : null}
          {localError ? (
            <p className="text-sm text-destructive">{localError}</p>
          ) : null}
          <p className="text-xs text-muted-foreground">
            Scanned documents without a text layer cannot be read yet.
          </p>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setIsOpen(false)}
            disabled={mutation.isPending}
          >
            Cancel
          </Button>
          <LoadingButton
            loading={mutation.isPending}
            disabled={!file}
            onClick={() => file && mutation.mutate(file)}
          >
            Upload and parse
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
