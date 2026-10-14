import { AlertCircle } from "lucide-react"
import { useState } from "react"
import FuelDemo from "./FuelDemo"
import { IntroTutorial } from "./IntroTutorial"

export function HowItWorks() {
  const [introDone, setIntroDone] = useState(false)

  return (
    <div className="space-y-3">
      <div className="flex items-start gap-3">
        <AlertCircle className="h-6 w-6 text-amber-500 flex-shrink-0 mt-1" />
        <div>
          <h1 className="text-2xl font-bold tracking-tight">How It Works</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Understand the optimization algorithm that powers Vector8's route
            planning
          </p>
        </div>
      </div>

      {introDone ? (
        <FuelDemo />
      ) : (
        <IntroTutorial onFinish={() => setIntroDone(true)} />
      )}
    </div>
  )
}

export default HowItWorks
