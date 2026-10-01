// @ts-nocheck
import {
  CAPACITY,
  cheapestPrice,
  MPG,
  RESERVE,
  STATIONS,
  TOTAL,
} from "@/lib/fuelSim"

const TICK_STEP = 100
const TICKS: number[] = []
for (let d = 0; d <= TOTAL; d += TICK_STEP) {
  if (TOTAL - d < 40 && d !== 0) continue // avoid crowding right next to DEST
  TICKS.push(d)
}

interface FuelTrackProps {
  title: string
  subtitle: string
  variant: string
  truckDist: number
  fuel: number
  decision: {
    head: string
    note: string
    figures: Array<[string, string, boolean?]> | null
  } | null
  visited: Set<string>
}

export default function FuelTrack({
  title,
  subtitle,
  variant,
  truckDist,
  fuel,
  decision,
  visited,
}: FuelTrackProps) {
  const reachMiles = Math.max(0, (fuel - RESERVE) * MPG)
  const fromPct = (truckDist / TOTAL) * 100
  const reachWidthPct = Math.min(100 - fromPct, (reachMiles / TOTAL) * 100)

  return (
    <div className={`fuel-track-block${variant ? ` variant-${variant}` : ""}`}>
      <div className="fuel-track-head">
        <span className="fuel-track-title">{title}</span>
        <span className="fuel-track-sub">{subtitle}</span>
      </div>

      <section className="fuel-stage">
        <div className="fuel-track">
          <div
            className="fuel-reach"
            style={{ left: `${fromPct}%`, width: `${reachWidthPct}%` }}
          />
          <div className="fuel-point start">START · 0 mi</div>
          <div className="fuel-point end">DEST · {TOTAL} mi</div>

          {TICKS.map((d) => (
            <div key={d}>
              <div
                className="fuel-tick"
                style={{ left: `${(d / TOTAL) * 100}%` }}
              />
              <div
                className={`fuel-tick-label${d === 0 ? " start" : ""}`}
                style={{ left: `${(d / TOTAL) * 100}%` }}
              >
                {d} mi
              </div>
            </div>
          ))}

          {STATIONS.map((s) => (
            <div
              key={s.name}
              className={
                "fuel-station" +
                (s.price === cheapestPrice ? " cheapest" : "") +
                (visited.has(s.name) ? " visited" : "")
              }
              style={{ left: `${(s.dist / TOTAL) * 100}%` }}
            >
              <div className="price">${s.price.toFixed(2)}</div>
              <div className="dot" />
            </div>
          ))}

          <div className="fuel-truck" style={{ left: `${fromPct}%` }}>
            <span className="fuel-truck-flip">🚛</span>
          </div>
          <div className="fuel-mile-tag" style={{ left: `${fromPct}%` }}>
            {truckDist.toFixed(0)} mi
          </div>
        </div>

        <div className="fuel-gaugewrap">
          <div className="fuel-gaugelabel">
            Fuel {fuel.toFixed(1)} / {CAPACITY} gal
          </div>
          <div className="fuel-gauge">
            <div
              className="fuel-gaugefill"
              style={{ width: `${(fuel / CAPACITY) * 100}%` }}
            />
          </div>
          <div className="fuel-gaugelabel dist">
            Distance <b>{truckDist.toFixed(0)}</b> / {TOTAL} mi traveled ·{" "}
            <b>{(TOTAL - truckDist).toFixed(0)}</b> mi remaining
          </div>
        </div>
      </section>

      {decision && (
        <section className="fuel-decision">
          <div className="fuel-decision-head">{decision.head}</div>
          <div className="fuel-decision-body">
            <div>{decision.note}</div>
            {decision.figures && (
              <div className="fuel-figures">
                {decision.figures.map(([label, value, highlight]) => (
                  <div key={label}>
                    <span>{label}</span>
                    <b className={highlight ? "highlight" : undefined}>
                      {value}
                    </b>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
