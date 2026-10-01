// @ts-nocheck
export const MPG = 6.8
export const CAPACITY = 150
export const RESERVE = 20
export const START_FUEL = 62
export const TOTAL = 860
const GPM = 1 / MPG

export const STATIONS = [
  { name: "Station A", dist: 140, price: 5.19 },
  { name: "Station B", dist: 260, price: 6.29 },
  { name: "Station C", dist: 430, price: 6.15 },
  { name: "Station D", dist: 590, price: 4.99 },
  { name: "Station E", dist: 760, price: 6.09 },
]

export const cheapestPrice = Math.min(...STATIONS.map((s) => s.price))

/**
 * Greedy look-ahead strategy: at each stop, find the next station (or the
 * destination) with a lower price. If reachable, buy only enough to get
 * there with RESERVE left. If no cheaper station exists ahead, top up
 * enough to cover the rest of the trip (capped by tank capacity).
 */
export function computeGreedy() {
  let fuel = START_FUEL
  let pos = 0
  let cost = 0
  const steps = []
  const points = [...STATIONS, { dist: TOTAL, price: null, isDest: true }]

  for (let i = 0; i < points.length; i++) {
    const st = points[i]
    const used = (st.dist - pos) * GPM
    const fuelOnArrival = fuel - used
    pos = st.dist

    if (st.isDest) {
      steps.push({ isDest: true, dist: st.dist, fuelOnArrival })
      fuel = fuelOnArrival
      break
    }

    let target = null
    for (let j = i + 1; j < points.length; j++) {
      const c = points[j]
      if (c.isDest || c.price < st.price) {
        target = c
        break
      }
    }

    const hasCheaperTarget = !!(target && !target.isDest)
    const need = hasCheaperTarget
      ? (target.dist - st.dist) * GPM + RESERVE
      : (TOTAL - st.dist) * GPM + RESERVE
    const purchase = Math.max(
      0,
      Math.min(CAPACITY - fuelOnArrival, need - fuelOnArrival),
    )

    fuel = fuelOnArrival + purchase
    cost += purchase * st.price
    steps.push({
      station: st,
      fuelOnArrival,
      purchase,
      fuelAfter: fuel,
      target,
      hasCheaperTarget,
    })
  }

  return { steps, cost }
}

/** Naive baseline: refuel at every stop, just enough to reach the next one, no price awareness. */
export function computeNaive() {
  let fuel = START_FUEL
  let pos = 0
  let cost = 0
  const steps = []
  const points = [...STATIONS, { dist: TOTAL, isDest: true }]

  for (let i = 0; i < points.length; i++) {
    const st = points[i]
    const used = (st.dist - pos) * GPM
    const fuelOnArrival = fuel - used
    pos = st.dist

    if (st.isDest) {
      steps.push({ isDest: true, dist: st.dist, fuelOnArrival })
      fuel = fuelOnArrival
      break
    }

    const next = points[i + 1]
    const need = (next.dist - st.dist) * GPM + RESERVE
    const purchase = Math.max(
      0,
      Math.min(CAPACITY - fuelOnArrival, need - fuelOnArrival),
    )

    fuel = fuelOnArrival + purchase
    cost += purchase * st.price
    steps.push({ station: st, fuelOnArrival, purchase, fuelAfter: fuel, next })
  }

  return { steps, cost }
}

/** Convenience wrapper — total cost only. */
export function computeNaiveCost() {
  return computeNaive().cost
}

/**
 * "Fill for the trip" baseline: at every stop, buys enough to cover the
 * REST of the trip plus reserve (capped by tank capacity) — no price
 * comparison at all. Because the tank is large enough to cover most of the
 * remaining distance in one go, this typically buys almost everything at
 * whichever station it happens to stop at first, then nothing further.
 * Same total gallons purchased as the other two strategies — only where
 * they're bought differs, which is what makes the cost comparison fair.
 */
export function computeNaiveFull() {
  let fuel = START_FUEL
  let pos = 0
  let cost = 0
  const steps = []
  const points = [...STATIONS, { dist: TOTAL, isDest: true }]

  for (let i = 0; i < points.length; i++) {
    const st = points[i]
    const used = (st.dist - pos) * GPM
    const fuelOnArrival = fuel - used
    pos = st.dist

    if (st.isDest) {
      steps.push({ isDest: true, dist: st.dist, fuelOnArrival })
      fuel = fuelOnArrival
      break
    }

    const remain = TOTAL - st.dist
    const need = remain * GPM + RESERVE
    const purchase = Math.max(
      0,
      Math.min(CAPACITY - fuelOnArrival, need - fuelOnArrival),
    )

    fuel = fuelOnArrival + purchase
    cost += purchase * st.price
    steps.push({ station: st, fuelOnArrival, purchase, fuelAfter: fuel })
  }

  return { steps, cost }
}

export const money = (v) => `$${v.toFixed(2)}`
export const gal = (v) => `${v.toFixed(1)} gal`
