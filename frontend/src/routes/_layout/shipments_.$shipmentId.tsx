/**
 * Shipment review page.
 *
 * Puts the original document next to the extracted fields so a dispatcher can
 * verify and correct what the parser produced. The trailing underscore keeps
 * this page out of the shipments list layout.
 */

import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import {
  createFileRoute,
  Link,
  redirect,
  useNavigate,
} from "@tanstack/react-router"
import { AlertTriangle, ArrowLeft, RefreshCw, Trash2 } from "lucide-react"
import { Suspense, useState } from "react"
import { ShipmentsService, UsersService } from "@/client"
import DocumentViewer from "@/components/Shipments/DocumentViewer"
import PlanTripDialog from "@/components/Shipments/PlanTripDialog"
import ShipmentForm from "@/components/Shipments/ShipmentForm"
import { Badge } from "@/components/ui/badge"
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
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/shipments_/$shipmentId")({
  component: ShipmentDetail,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (user.role === "driver") {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({
    meta: [{ title: "Shipment - Vector8" }],
  }),
})

function getShipmentQueryOptions(shipmentId: string) {
  return {
    queryFn: async () =>
      (
        await ShipmentsService.getShipment({
          path: { shipment_id: shipmentId },
        })
      ).data,
    queryKey: ["shipment", shipmentId],
  }
}

function getValidationQueryOptions(shipmentId: string) {
  return {
    queryFn: async () =>
      (
        await ShipmentsService.validateShipment({
          path: { shipment_id: shipmentId },
        })
      ).data,
    queryKey: ["shipment-validation", shipmentId],
  }
}

function ValidationIssues({ shipmentId }: { shipmentId: string }) {
  const { data: issues } = useSuspenseQuery(
    getValidationQueryOptions(shipmentId),
  )

  if (!issues || issues.length === 0) {
    return (
      <div className="vector8-surface p-4 text-sm text-muted-foreground">
        This shipment has everything the planner needs.
      </div>
    )
  }

  return (
    <div className="vector8-surface space-y-2 p-4">
      <p className="flex items-center gap-2 text-sm font-medium">
        <AlertTriangle className="size-4 text-amber-500" />
        Not ready for planning
      </p>
      <ul className="space-y-1 text-sm text-muted-foreground">
        {issues.map((issue) => (
          <li key={`${issue.field}-${issue.message}`}>
            <span className="font-mono text-xs">{issue.field}</span> —{" "}
            {issue.message}
          </li>
        ))}
      </ul>
    </div>
  )
}

function ShipmentDetailContent() {
  const { shipmentId } = Route.useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const { data: shipment } = useSuspenseQuery(
    getShipmentQueryOptions(shipmentId),
  )
  const canDelete =
    !!user &&
    (user.is_superuser ||
      user.role === "admin" ||
      (user.role === "dispatcher" && shipment?.owner_id === user.id))

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["shipments"] })
    queryClient.invalidateQueries({ queryKey: ["shipment", shipmentId] })
    queryClient.invalidateQueries({
      queryKey: ["shipment-validation", shipmentId],
    })
  }

  const reparse = useMutation({
    mutationFn: async () =>
      (
        await ShipmentsService.reparseShipment({
          path: { shipment_id: shipmentId },
        })
      ).data,
    onSuccess: () => {
      showSuccessToast("Document parsed again. Manual edits were replaced.")
      invalidate()
    },
    onError: (error: Error) => handleError.call(showErrorToast, error),
  })

  const remove = useMutation({
    mutationFn: async () =>
      ShipmentsService.deleteShipment({ path: { shipment_id: shipmentId } }),
    onSuccess: () => {
      showSuccessToast("Shipment deleted.")
      setConfirmDelete(false)
      queryClient.invalidateQueries({ queryKey: ["shipments"] })
      navigate({ to: "/shipments" })
    },
    onError: (error: Error) => handleError.call(showErrorToast, error),
  })

  if (!shipment) {
    return null
  }

  const latestDocument = shipment.documents?.[0]
  const failedDocument =
    latestDocument?.parse_status === "failed" ? latestDocument : null

  return (
    <div className="flex flex-col gap-6">
      <div className="vector8-page-header flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-2">
          <Button variant="ghost" size="sm" asChild className="-ml-2">
            <Link to="/shipments">
              <ArrowLeft className="size-4" />
              Shipments
            </Link>
          </Button>
          <h1 className="text-3xl font-semibold tracking-tight">
            {shipment.reference_number ?? "Shipment"}
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{shipment.planning_status}</Badge>
            {shipment.is_manually_edited ? (
              <Badge variant="outline">Edited by hand</Badge>
            ) : null}
            {shipment.extraction_confidence ? (
              <span className="text-sm text-muted-foreground">
                Extraction confidence{" "}
                {Math.round(Number(shipment.extraction_confidence) * 100)}%
              </span>
            ) : null}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <PlanTripDialog shipmentId={shipmentId} />
          <Button
            variant="outline"
            onClick={() => reparse.mutate()}
            disabled={reparse.isPending || !latestDocument}
          >
            <RefreshCw
              className={`size-4 ${reparse.isPending ? "animate-spin" : ""}`}
            />
            Re-parse
          </Button>
          {canDelete ? (
            <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
              <Button
                variant="destructive"
                onClick={() => setConfirmDelete(true)}
                disabled={remove.isPending}
              >
                <Trash2 className="size-4" />
                Delete
              </Button>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Delete shipment?</DialogTitle>
                  <DialogDescription>
                    This removes the shipment, its stops and the attached
                    document. This cannot be undone.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <DialogClose asChild>
                    <Button variant="outline">Cancel</Button>
                  </DialogClose>
                  <LoadingButton
                    variant="destructive"
                    loading={remove.isPending}
                    onClick={() => remove.mutate()}
                  >
                    Delete
                  </LoadingButton>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          ) : null}
        </div>
      </div>

      {failedDocument ? (
        <div className="vector8-surface space-y-1 p-4">
          <p className="flex items-center gap-2 text-sm font-medium">
            <AlertTriangle className="size-4 text-destructive" />
            The last parse attempt failed
          </p>
          <p className="text-sm text-muted-foreground">
            {failedDocument.parse_error ?? "No details were recorded."}
          </p>
        </div>
      ) : null}

      <Suspense fallback={<Skeleton className="h-20 w-full" />}>
        <ValidationIssues shipmentId={shipmentId} />
      </Suspense>

      <div className="grid gap-6 xl:grid-cols-2">
        {latestDocument ? (
          <DocumentViewer document={latestDocument} />
        ) : (
          <div className="vector8-surface p-4 text-sm text-muted-foreground">
            No original document is attached to this shipment.
          </div>
        )}
        <ShipmentForm key={shipment.updated_at} shipment={shipment} />
      </div>
    </div>
  )
}

function ShipmentDetail() {
  return (
    <Suspense fallback={<Skeleton className="h-[80vh] w-full" />}>
      <ShipmentDetailContent />
    </Suspense>
  )
}
