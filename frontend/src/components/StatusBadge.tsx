import { useEffect, useRef, useState, type CSSProperties } from 'react'

import { cn } from '@/lib/utils'
import type { ClaimStatus, ThesisStatus, Verdict } from '@/lib/api'

/** Everything this badge can render: thesis status, claim status, or an evidence verdict. */
export type BadgeStatus = ThesisStatus | ClaimStatus | Verdict

/**
 * THE ONE HOME FOR STATUS → COLOUR. Every consumer of a status colour reads this
 * map — the badge below, the left spine on status-bearing cards, and the chart's
 * annotations. Each value is a design token name, resolved to `var(--…)` by
 * `statusColor()`, so nothing downstream hard-codes a hex or a Tailwind class.
 *
 * Every value in the backend's vocabulary (backend/domain/status.py and the
 * verification verdicts) is listed explicitly, and the Record type makes that
 * exhaustive — adding a status there surfaces as a type error here rather than
 * as a silently grey badge and a colourless spine.
 */
const STATUS_TOKEN: Record<BadgeStatus, string> = {
  // Thesis statuses
  strengthening: '--status-strengthening',
  weakening: '--status-weakening',
  breaking: '--status-broken',

  // Claim statuses ('weakening' and 'pending' are shared with the set above)
  strongly_supported: '--status-supported',
  supported: '--status-supported',
  broken: '--status-broken',
  pending: '--status-pending',

  // Evidence verdicts
  supports: '--status-supported',
  contradicts: '--status-broken',
  neutral: '--status-pending',
}

/**
 * The CSS colour for a status, e.g. `var(--status-broken)`.
 *
 * Returns the pending (muted) colour for anything unrecognised rather than
 * throwing or returning transparent — an unknown status should read as "no
 * signal", never as invisible.
 */
export function statusColor(status: string | null | undefined): string {
  const token = (status && STATUS_TOKEN[status as BadgeStatus]) || '--status-pending'
  return `var(${token})`
}

/**
 * Fires once when `status` becomes something it was not, and never on the way in.
 *
 * ⚠️ THE PREVIOUS VALUE IS SEEDED WITH THE FIRST ONE, so the opening render can
 * never look like a change. Without that, arriving on a page would set every
 * badge on it pulsing at once — which would say "these all just changed" about
 * data that has simply been loaded.
 *
 * The flag clears on animationend rather than a timer, so it can never be left
 * set by a badge that unmounted mid-pulse.
 */
function useStatusPulse(status: BadgeStatus): {
  pulsing: boolean
  onAnimationEnd: () => void
} {
  const [pulsing, setPulsing] = useState(false)
  const previous = useRef(status)

  useEffect(() => {
    if (previous.current === status) return
    previous.current = status
    setPulsing(true)
  }, [status])

  return { pulsing, onAnimationEnd: () => setPulsing(false) }
}

/**
 * Outlined, uppercase, mono status pill. Colour is never the only signal — the
 * label always spells the status out (`whitespace-nowrap` keeps "STRONGLY
 * SUPPORTED" on one line).
 */
export function StatusBadge({
  status,
  className,
}: {
  status: BadgeStatus
  className?: string
}) {
  const color = statusColor(status)
  const { pulsing, onAnimationEnd } = useStatusPulse(status)

  return (
    <span
      className={cn(
        // `relative` anchors the pulse's glow pseudo-element; it is inert
        // otherwise.
        'relative inline-flex w-fit shrink-0 items-center whitespace-nowrap rounded-[4px] border bg-transparent px-[9px] py-[3px] font-mono text-[10.5px] leading-none tracking-[0.08em] uppercase',
        pulsing && 'status-pulse',
        className,
      )}
      // Inline rather than Tailwind classes so this reads from STATUS_TOKEN like
      // every other consumer. A class map would be a second copy of the same
      // mapping, and the two would drift the first time a status was added.
      // The border keeps its previous 50% strength via color-mix.
      style={
        {
          color,
          borderColor: `color-mix(in srgb, ${color} 50%, transparent)`,
          // Read by .status-pulse::after — the flash is the colour just arrived at.
          '--status-glow': `color-mix(in srgb, ${color} 45%, transparent)`,
        } as CSSProperties
      }
      onAnimationEnd={onAnimationEnd}
    >
      {status.replace(/_/g, ' ')}
    </span>
  )
}
