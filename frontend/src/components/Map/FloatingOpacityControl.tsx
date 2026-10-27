import {
  FLOATING_OPACITY_MIN,
  setFloatingOpacity,
  useFloatingOpacity,
} from "@/hooks/useFloatingOpacity"

export function FloatingOpacityControl() {
  const opacity = useFloatingOpacity()

  return (
    <label className="pointer-events-auto absolute bottom-4 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2 rounded-md border border-border/70 bg-white px-3 py-1.5 text-xs text-muted-foreground shadow-md dark:bg-slate-950">
      <span>Opacity</span>
      <input
        type="range"
        min={FLOATING_OPACITY_MIN}
        max={1}
        step={0.05}
        value={opacity}
        onChange={(event) => setFloatingOpacity(Number(event.target.value))}
        aria-label="Floating elements opacity"
        className="h-1 w-32 cursor-pointer accent-primary"
      />
      <span className="w-9 text-right tabular-nums">
        {Math.round(opacity * 100)}%
      </span>
    </label>
  )
}
