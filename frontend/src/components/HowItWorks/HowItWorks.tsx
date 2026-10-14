import { useState } from "react"
import FuelDemo from "./FuelDemo"
import { IntroTutorial } from "./IntroTutorial"

export function HowItWorks() {
  const [introDone, setIntroDone] = useState(false)

  return (
    <div className="space-y-3">
      <div className="text-center">
        <h1 className="text-2xl font-bold tracking-tight">How It Works</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Understand the optimization algorithm that powers Vector8's route
          planning
        </p>
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
