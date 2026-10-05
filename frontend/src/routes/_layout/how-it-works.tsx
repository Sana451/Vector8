import { createFileRoute } from "@tanstack/react-router"
import { HowItWorks } from "@/components/HowItWorks/HowItWorks"

export const Route = createFileRoute("/_layout/how-it-works")({
  component: HowItWorksPage,
})

function HowItWorksPage() {
  return <HowItWorks />
}
