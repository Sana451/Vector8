import { useCallback, useEffect, useState } from "react"

interface IntroStep {
  key: string
  icon?: { symbol: string; className: string }
  title: string
  body: string
}

const STEPS: IntroStep[] = [
  {
    key: "algorithm",
    title: "The Smart Optimization Algorithm",
    body: "Vector8 uses a sophisticated greedy look-ahead algorithm to optimize operational costs in real-world scenarios. Unlike naive strategies that ignore market conditions or fill tanks unnecessarily, our algorithm makes informed decisions by analyzing future opportunities.",
  },
  {
    key: "smart",
    icon: { symbol: "✓", className: "text-green-600" },
    title: "Smart Strategy",
    body: "Looks ahead for better opportunities before committing to purchases, ensuring every decision maximizes long-term value.",
  },
  {
    key: "naive",
    icon: { symbol: "✗", className: "text-red-600" },
    title: "Naive Approaches",
    body: "Traditional methods either ignore market conditions entirely or lock in suboptimal decisions without considering future opportunities.",
  },
  {
    key: "demo",
    title: "Interactive Demo",
    body: "Next you'll see the same truck traveling the same route using three different strategies. Watch how the greedy algorithm outperforms both naive baselines by making smarter purchasing decisions based on real-time price signals.",
  },
]

interface IntroTutorialProps {
  onFinish: () => void
}

export function IntroTutorial({ onFinish }: IntroTutorialProps) {
  const [index, setIndex] = useState(0)
  const step = STEPS[index]

  const advance = useCallback(() => {
    if (index >= STEPS.length - 1) {
      onFinish()
    } else {
      setIndex(index + 1)
    }
  }, [index, onFinish])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onFinish()
      } else if (event.key === "ArrowRight") {
        advance()
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [advance, onFinish])

  return (
    <div className="relative flex min-h-[60vh] items-center justify-center">
      <button
        type="button"
        onClick={onFinish}
        className="absolute right-0 top-0 z-10 rounded border border-border bg-background px-3 py-1 text-xs font-medium text-muted-foreground hover:bg-muted"
      >
        Skip
      </button>

      <button
        type="button"
        onClick={advance}
        aria-label="Continue"
        className="flex min-h-[60vh] w-full cursor-pointer flex-col items-center justify-center gap-6 rounded-lg px-6 text-center outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div
          key={step.key}
          aria-live="polite"
          className="max-w-2xl space-y-4 duration-300 animate-in fade-in zoom-in-95"
        >
          {step.icon && (
            <div className={`text-6xl font-bold ${step.icon.className}`}>
              {step.icon.symbol}
            </div>
          )}
          <h2 className="text-3xl font-bold tracking-tight">{step.title}</h2>
          <p className="text-lg leading-relaxed text-muted-foreground">
            {step.body}
          </p>
        </div>

        <div className="flex flex-col items-center gap-2">
          <div className="flex gap-1.5">
            {STEPS.map((s, i) => (
              <span
                key={s.key}
                className={`h-1.5 w-1.5 rounded-full ${
                  i === index ? "bg-primary" : "bg-muted-foreground/30"
                }`}
              />
            ))}
          </div>
          <span className="text-xs text-muted-foreground">
            Click to continue
          </span>
        </div>
      </button>
    </div>
  )
}

export default IntroTutorial
