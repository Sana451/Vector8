import { AlertCircle } from "lucide-react"
import FuelDemo from "./FuelDemo"

export function HowItWorks() {
  return (
    <div className="space-y-6">
      {/* Вводная секция */}
      <div className="space-y-4">
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

        <div className="bg-card border border-border/50 rounded-lg p-6 space-y-4">
          <div>
            <h2 className="font-semibold text-base mb-2">
              The Smart Optimization Algorithm
            </h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Vector8 uses a sophisticated greedy look-ahead algorithm to
              optimize operational costs in real-world scenarios. Unlike naive
              strategies that ignore market conditions or fill tanks
              unnecessarily, our algorithm makes informed decisions by analyzing
              future opportunities.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="space-y-2">
              <h3 className="font-medium text-sm flex items-center gap-2">
                <span className="text-green-600">✓</span> Smart Strategy
              </h3>
              <p className="text-xs text-muted-foreground">
                Looks ahead for better opportunities before committing to
                purchases, ensuring every decision maximizes long-term value.
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="font-medium text-sm flex items-center gap-2">
                <span className="text-red-600">✗</span> Naive Approaches
              </h3>
              <p className="text-xs text-muted-foreground">
                Traditional methods either ignore market conditions entirely or
                lock in suboptimal decisions without considering future
                opportunities.
              </p>
            </div>
          </div>

          <div className="pt-2 border-t border-border/50">
            <p className="text-xs text-muted-foreground">
              <strong>Interactive Demo:</strong> Below you'll see the same truck
              traveling the same route using three different strategies. Watch
              how the greedy algorithm outperforms both naive baselines by
              making smarter purchasing decisions based on real-time price
              signals.
            </p>
          </div>
        </div>
      </div>

      {/* Интерактивное демо */}
      <FuelDemo />
    </div>
  )
}

export default HowItWorks
