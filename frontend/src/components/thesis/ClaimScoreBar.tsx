import { statusColor } from '@/components/StatusBadge'
import { Tooltip, TooltipValue } from '@/components/ui/tooltip'
import type { ClaimStatus } from '@/lib/api'

/** +1.67, -1.90, 0.00 — always signed, always two places, so a column of them
 *  lines up and a gain is never mistaken for a loss at a glance. */
function formatScore(score: number): string {
  return `${score > 0 ? '+' : score < 0 ? '−' : ''}${Math.abs(score).toFixed(2)}`
}

/**
 * Where a claim's score sits between breaking and strongly supported.
 *
 * ⚠️ THIS IS THE POINT OF THE WHOLE SECTION. Before it, the engine's verdict
 * arrived as a bare word: a claim reading SUPPORTED with a contradiction against
 * it looked like a mistake, and there was no way to see that the supporting
 * evidence had simply outweighed it. The number and its position on the scale
 * are the reasoning, shown.
 *
 * ⚠️ THE SCALE IS NOT A CLAMP ON THE SCORE. `score_scale` is the range the BANDS
 * span, and a real score can sit outside it — four contradictions at high
 * confidence score -1.90 against a floor of -1.00. The marker clamps to the end
 * of the track; the number beside it never does, because that would report a
 * figure the engine did not compute.
 */
export function ClaimScoreBar({
  score,
  scale,
  status,
}: {
  /** Null when the claim has no evidence — nothing to place. */
  score: number | null
  scale: [number, number]
  status: ClaimStatus
}) {
  if (score === null) {
    return (
      <span className="font-mono text-2xs text-text-muted">
        no score yet
      </span>
    )
  }

  const [floor, ceiling] = scale
  const fraction = (score - floor) / (ceiling - floor)
  const clamped = Math.min(Math.max(fraction, 0), 1)
  const beyond = fraction < 0 || fraction > 1

  return (
    <Tooltip
      content={
        <>
          Weighted score <TooltipValue>{formatScore(score)}</TooltipValue> —
          supporting confidence minus contradicting, on a scale from{' '}
          <TooltipValue>{formatScore(floor)}</TooltipValue> (breaking) to{' '}
          <TooltipValue>{formatScore(ceiling)}</TooltipValue> (strongly supported)
          {beyond && '. This claim sits past the end of that scale.'}
        </>
      }
    >
      <span className="flex cursor-help items-center gap-2">
        <span
          className="font-mono text-2xs tabular-nums"
          style={{ color: statusColor(status) }}
        >
          {formatScore(score)}
        </span>
        {/* The track is the full band range; the marker is a position on it, not
            a fill from one end — a score is a point, not a quantity. */}
        <span
          aria-hidden
          className="relative h-1 w-20 shrink-0 overflow-hidden rounded-full bg-border/60"
        >
          {/* Zero, where support and contradiction cancel. A tick rather than a
              label: it is a reference point, not a reading. */}
          <span
            className="absolute top-0 h-full w-px bg-text-muted/50"
            style={{ left: `${((0 - floor) / (ceiling - floor)) * 100}%` }}
          />
          <span
            className="absolute top-0 h-full w-1 rounded-full"
            style={{
              // translateX(-50%) so the marker is CENTRED on its value; without
              // it, every score would read half a marker high.
              left: `${clamped * 100}%`,
              transform: 'translateX(-50%)',
              backgroundColor: statusColor(status),
            }}
          />
        </span>
      </span>
    </Tooltip>
  )
}
