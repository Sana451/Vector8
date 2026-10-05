// @ts-nocheck
import { useMemo, useState } from "react"
import {
  CAPACITY,
  computeGreedy,
  computeNaive,
  computeNaiveFull,
  gal,
  MPG,
  money,
  RESERVE,
  START_FUEL,
  TOTAL,
} from "@/lib/fuelSim"
import FuelTrack from "./FuelTrack"
import "@/styles/fuel-demo.css"

const wait = (ms: number): Promise<void> =>
  new Promise((r) => setTimeout(r, ms))

interface Step {
  isDest?: boolean
  dist?: number
  fuelOnArrival: number
  station?: { name: string; dist: number; price: number }
  purchase?: number
  fuelAfter?: number
  target?: { name: string; dist: number; price: number; isDest?: boolean }
  hasCheaperTarget?: boolean
  next?: { isDest?: boolean; name?: string; dist: number }
}

interface Decision {
  head: string
  note: string
  figures: Array<[string, string, boolean?]> | null
}

// Initial decision for the starting point (idx = -1)
function getInitialDecision(): Decision {
  return {
    head: "START — Ready to depart",
    note: "Begin the journey with a full tank. Different strategies will make different decisions at each stop along the way.",
    figures: [
      ["Current fuel", gal(START_FUEL)],
      ["Remaining trip", `${TOTAL} mi`],
      ["Reserve kept", gal(RESERVE)],
      ["Purchase", gal(0), true],
    ],
  }
}

function decisionForGreedy(step: Step): Decision {
  if (step.isDest) {
    return {
      head: "ARRIVED",
      note: `Destination reached with ${gal(step.fuelOnArrival)} in the tank — right at the safety reserve, nothing wasted.`,
      figures: null,
    }
  }
  const head = step.hasCheaperTarget
    ? `CHEAPER STATION AHEAD → ${step.target.name} @ ${money(step.target.price)}`
    : "NO CHEAPER REACHABLE STATION"
  const note = step.hasCheaperTarget
    ? step.purchase < 0.05
      ? "Don't fill the tank. Current fuel already covers the leg to the cheaper station."
      : `Don't top off here. Buy only enough to safely reach ${step.target.name}.`
    : "This is the best price available before the destination. Fill enough to cover the rest of the trip."
  const figures = step.hasCheaperTarget
    ? [
        ["Current fuel", gal(step.fuelOnArrival)],
        [
          "Distance to target",
          `${(step.target.dist - step.station.dist).toFixed(0)} mi`,
        ],
        ["Reserve kept", gal(RESERVE)],
        ["Purchase", gal(step.purchase), true],
      ]
    : [
        ["Current fuel", gal(step.fuelOnArrival)],
        ["Remaining trip", `${(TOTAL - step.station.dist).toFixed(0)} mi`],
        ["Reserve kept", gal(RESERVE)],
        ["Purchase", gal(step.purchase), true],
      ]
  return { head, note, figures }
}

function decisionForNaive(step: Step): Decision {
  if (step.isDest) {
    return {
      head: "ARRIVED",
      note: `Destination reached with ${gal(step.fuelOnArrival)} left — no price check along the way, so more was spent overall.`,
      figures: null,
    }
  }
  const nextLabel = step.next.isDest ? "the destination" : step.next.name
  return {
    head: "REFUEL — no price check",
    note: `Top up just enough to reach ${nextLabel}. Price at this station isn't part of the decision.`,
    figures: [
      ["Current fuel", gal(step.fuelOnArrival)],
      [
        "Distance to next stop",
        `${(step.next.dist - step.station.dist).toFixed(0)} mi`,
      ],
      ["Reserve kept", gal(RESERVE)],
      ["Purchase", gal(step.purchase), true],
    ],
  }
}

function decisionForNaiveFull(step: Step): Decision {
  if (step.isDest) {
    return {
      head: "ARRIVED",
      note: `Destination reached with ${gal(step.fuelOnArrival)} left — right at the safety reserve. Same total fuel as the other two strategies, just bought at a different stop.`,
      figures: null,
    }
  }
  const remain = TOTAL - step.station.dist
  if (step.purchase < 0.05) {
    return {
      head: "ALREADY ENOUGH FUEL",
      note: "Current fuel already covers the rest of the trip with reserve to spare — no price comparison needed, no purchase here.",
      figures: [
        ["Current fuel", gal(step.fuelOnArrival)],
        ["Remaining trip", `${remain.toFixed(0)} mi`],
        ["Reserve kept", gal(RESERVE)],
        ["Purchase", gal(step.purchase), true],
      ],
    }
  }
  return {
    head: "TOP UP FOR THE REST OF THE TRIP",
    note: "No price comparison — just buy enough (plus reserve) to reach the destination from here.",
    figures: [
      ["Current fuel", gal(step.fuelOnArrival)],
      ["Remaining trip", `${remain.toFixed(0)} mi`],
      ["Reserve kept", gal(RESERVE)],
      ["Purchase", gal(step.purchase), true],
    ],
  }
}

const snapshotDist = (step: Step): number =>
  step.isDest ? step.dist || 0 : step.station?.dist || 0
const snapshotFuel = (step: Step): number =>
  step.isDest ? step.fuelOnArrival : step.fuelAfter || 0

interface Strategy {
  key: string
  title: string
  subtitle: string
  variant: string
  compute: () => { steps: Step[]; cost: number }
  decisionFor: (step: Step) => Decision
}

const STRATEGIES: Strategy[] = [
  {
    key: "full",
    title: "🚫 Fill for the trip",
    subtitle: "Buys enough to finish the trip wherever it can, ignores price",
    variant: "naive-full",
    compute: computeNaiveFull,
    decisionFor: decisionForNaiveFull,
  },
  {
    key: "jit",
    title: "🚫 Just enough",
    subtitle: "Refuels at every stop, no price awareness",
    variant: "naive",
    compute: computeNaive,
    decisionFor: decisionForNaive,
  },
  {
    key: "greedy",
    title: "✅ Greedy",
    subtitle: "Price-aware, looks ahead before buying",
    variant: "greedy",
    compute: computeGreedy,
    decisionFor: decisionForGreedy,
  },
]

export default function FuelDemo() {
  const results = useMemo(
    () => STRATEGIES.map((s) => ({ ...s, ...s.compute() })), // adds .steps and .cost
    [],
  )

  const [idx, setIdx] = useState(-1) // -1 = not started
  const [maxIdx, setMaxIdx] = useState(-1)
  const [busy, setBusy] = useState(false)
  const [truckDist, setTruckDist] = useState(0) // same distances on every track
  const [fuels, setFuels] = useState(() =>
    Object.fromEntries(STRATEGIES.map((s) => [s.key, START_FUEL])),
  )
  const [decisions, setDecisions] = useState(() => {
    // Initialize decisions for the starting point (idx = -1)
    const initialDecisions: Record<string, Decision | null> = {}
    for (const r of results) {
      initialDecisions[r.key] = getInitialDecision()
    }
    return initialDecisions
  })
  const [visitedMap, setVisitedMap] = useState(() =>
    Object.fromEntries(STRATEGIES.map((s) => [s.key, new Set()])),
  )

  const isDone = idx >= 0 && results[0].steps[idx].isDest

  function namesUpTo(steps: Step[], i: number): Set<string> {
    const s = new Set<string>()
    for (let k = 0; k <= i; k++) {
      const st = steps[k]
      if (!st.isDest) s.add(st.station?.name || "")
    }
    return s
  }

  function resetToIdle(): void {
    setIdx(-1)
    setTruckDist(0)
    setFuels(Object.fromEntries(STRATEGIES.map((s) => [s.key, START_FUEL])))
    // Reset decisions to initial state
    const initialDecisions: Record<string, Decision | null> = {}
    for (const r of results) {
      initialDecisions[r.key] = getInitialDecision()
    }
    setDecisions(initialDecisions)
    setVisitedMap(Object.fromEntries(STRATEGIES.map((s) => [s.key, new Set()])))
  }

  // Instant jump — revisiting a step already seen. Every track moves together, no animation.
  function jumpTo(i: number): void {
    if (i === -1) {
      resetToIdle()
      return
    }
    const nextFuels: Record<string, number> = {}
    const nextDecisions: Record<string, Decision | null> = {}
    const nextVisited: Record<string, Set<string>> = {}
    for (const r of results) {
      const step = r.steps[i]
      nextFuels[r.key] = snapshotFuel(step)
      nextDecisions[r.key] = r.decisionFor(step)
      nextVisited[r.key] = namesUpTo(r.steps, i)
    }
    setTruckDist(snapshotDist(results[0].steps[i]))
    setFuels(nextFuels)
    setDecisions(nextDecisions)
    setVisitedMap(nextVisited)
    setIdx(i)
  }

  // Animated reveal — first time a step is reached. Every truck travels together.
  async function animateTo(i: number): Promise<void> {
    setBusy(true)
    const refStep = results[0].steps[i]

    setTruckDist(snapshotDist(refStep))
    setFuels(
      Object.fromEntries(results.map((r) => [r.key, r.steps[i].fuelOnArrival])),
    )
    await wait(920)

    const upto = refStep.isDest ? i - 1 : i
    setVisitedMap(
      Object.fromEntries(results.map((r) => [r.key, namesUpTo(r.steps, upto)])),
    )
    setDecisions(
      Object.fromEntries(
        results.map((r) => [r.key, r.decisionFor(r.steps[i])]),
      ),
    )

    const needsFill = results.some((r) => {
      const st = r.steps[i]
      return !st.isDest && st.purchase > 0.05
    })
    if (needsFill) {
      await wait(300)
      setFuels((prev) => {
        const next = { ...prev }
        for (const r of results) {
          const st = r.steps[i]
          if (!st.isDest && st.purchase > 0.05) next[r.key] = st.fuelAfter
        }
        return next
      })
    }

    setIdx(i)
    setMaxIdx((m) => Math.max(m, i))
    setBusy(false)
  }

  function handleNext(): void {
    const target = idx + 1
    if (target >= results[0].steps.length) return
    if (target > maxIdx) animateTo(target)
    else jumpTo(target)
  }
  function handleBack(): void {
    if (idx === -1) return
    jumpTo(idx - 1)
  }
  function handleReplay(): void {
    resetToIdle()
    setMaxIdx(-1)
  }

  const maxCost = Math.max(...results.map((r) => r.cost))
  const greedy = results.find((r) => r.key === "greedy")
  const naiveResults = results.filter((r) => r.key !== "greedy")

  return (
    <div className="fuel-demo">
      <div className="fuel-header">
        <span className="mark">⛽</span>
        <div>
          <div className="name">
            Smart Fuel Optimization — Greedy vs. two no-algorithm baselines
          </div>
          <div className="sub">
            Same truck, same route, same stations — only the buying decisions
            differ
          </div>
        </div>
      </div>

      <section className="fuel-truck-card">
        <div className="fuel-truck-title">🚛 Freightliner</div>
        <div className="fuel-truck-stats">
          <div>
            <span>Tank</span>
            <b>{CAPACITY} gal</b>
          </div>
          <div>
            <span>Start fuel</span>
            <b>{START_FUEL} gal</b>
          </div>
          <div>
            <span>Consumption</span>
            <b>{MPG} MPG</b>
          </div>
          <div>
            <span>Reserve</span>
            <b>{RESERVE} gal</b>
          </div>
        </div>
      </section>

      <div className="fuel-tracks">
        {results.map((r) => (
          <FuelTrack
            key={r.key}
            title={r.title}
            subtitle={r.subtitle}
            variant={r.variant}
            truckDist={truckDist}
            fuel={fuels[r.key]}
            decision={decisions[r.key] || null}
            visited={visitedMap[r.key]}
          />
        ))}
      </div>

      <div className="fuel-controls">
        <button
          type="button"
          className="fuel-btn ghost"
          onClick={handleBack}
          disabled={busy || idx === -1}
        >
          ← Back
        </button>
        {!isDone && (
          <button
            type="button"
            className="fuel-btn primary"
            onClick={handleNext}
            disabled={busy}
          >
            Next →
          </button>
        )}
        <button
          type="button"
          className="fuel-btn ghost"
          onClick={handleReplay}
          disabled={busy || idx === -1}
        >
          ↺ Replay
        </button>
      </div>

      {isDone && (
        <section className="fuel-compare">
          <h2>Three strategies, same route — real computed cost</h2>
          {results.map((r) => (
            <div className="fuel-bar-row" key={r.key}>
              <span>{r.title.replace(/^\S+\s/, "")}</span>
              <div className="fuel-bar">
                <div
                  className={`fuel-bar-fill ${r.variant}`}
                  style={{ width: `${(r.cost / maxCost) * 100}%` }}
                />
              </div>
              <b>{money(r.cost)}</b>
            </div>
          ))}
          {naiveResults.map((r) => (
            <div className="fuel-save" key={r.key}>
              <span>YOU SAVE vs "{r.title.replace(/^\S+\s/, "")}"</span>
              <b>{money(r.cost - greedy.cost)}</b>
            </div>
          ))}
        </section>
      )}
    </div>
  )
}
