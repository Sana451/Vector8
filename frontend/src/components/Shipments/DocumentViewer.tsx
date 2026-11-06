import { useQuery } from "@tanstack/react-query"
import { Download, FileWarning } from "lucide-react"
import { useEffect, useState } from "react"

import { type ShipmentDocumentPublic, ShipmentsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

/**
 * Renders the original upload next to the extracted fields.
 *
 * The file endpoint needs the bearer token, which an `<iframe src>` cannot
 * carry, so the bytes are fetched through the SDK and handed to the viewer as
 * an object URL.
 */
export default function DocumentViewer({
  document: documentMeta,
}: {
  document: ShipmentDocumentPublic
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)

  const {
    data: blob,
    isPending,
    isError,
  } = useQuery({
    queryKey: ["shipment-document", documentMeta.id],
    queryFn: async () =>
      (
        await ShipmentsService.downloadShipmentDocument({
          path: { document_id: documentMeta.id },
          responseType: "blob",
        })
      ).data as unknown as Blob,
    staleTime: Number.POSITIVE_INFINITY,
  })

  useEffect(() => {
    if (!blob) {
      return
    }
    const url = URL.createObjectURL(blob)
    setObjectUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [blob])

  if (isError) {
    return (
      <div className="vector8-surface flex flex-col items-center gap-2 p-6 text-center">
        <FileWarning className="size-6 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          The original file could not be loaded.
        </p>
      </div>
    )
  }

  if (isPending || !objectUrl) {
    return <Skeleton className="h-[70vh] w-full" />
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-sm text-muted-foreground">
          {documentMeta.filename} ({Math.round(documentMeta.size_bytes / 1024)}{" "}
          KB)
        </p>
        <Button variant="outline" size="sm" asChild>
          <a href={objectUrl} download={documentMeta.filename}>
            <Download className="size-4" />
            Download
          </a>
        </Button>
      </div>
      <iframe
        title={documentMeta.filename}
        src={objectUrl}
        className="h-[70vh] w-full rounded-lg border border-[var(--slate-border)]"
      />
    </div>
  )
}
