import { useEffect, useRef, useState, type CSSProperties } from 'react'

import { Tooltip, TooltipValue } from '@/components/ui/tooltip'
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
 * WHAT EACH STATUS ACTUALLY MEANS, in the reader's terms. A badge says
 * "WEAKENING"; this says what the app had to observe to put it there.
 *
 * Written from backend/domain/status.py so the two cannot drift into telling
 * different stories: claim statuses are score bands over supporting minus
 * contradicting evidence weighted by confidence, and a thesis rolls its claims
 * up — one broken CORE claim breaks the thesis, any other broken or weakening
 * claim only weakens it. Exhaustive by the same Record type as STATUS_TOKEN, so
 * a new status is a type error here rather than a silently unexplained pill.
 */
const STATUS_MEANING: Record<BadgeStatus, string> = {
  // Thesis statuses — rolled up from the claims below.
  strengthening: 'Every claim is holding up, and none has been contradicted.',
  weakening: 'At least one claim has picked up more contradicting evidence than support.',
  breaking: 'A claim you marked core has broken.',

  // Claim statuses — score bands over the evidence gathered for that claim.
  strongly_supported: 'Supporting evidence heavily outweighs anything contradicting it.',
  supported: 'More supporting evidence than contradicting, but not decisively.',
  broken: 'Contradicting evidence clearly outweighs the support.',
  pending: 'No evidence gathered yet — nothing has been checked against this.',

  // Evidence verdicts — one document's read of one claim.
  supports: 'This evidence backs the claim up.',
  contradicts: 'This evidence cuts against the claim.',
  neutral: 'This evidence bears on the claim without settling it either way.',
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
    // The label is a term of art — "WEAKENING" tells you the direction but not
    // what was observed to earn it. The tooltip carries that, on every badge, so
    // the vocabulary is explained wherever it is met rather than in one place a
    // reader has to go looking for.
    <Tooltip
      content={
        <>
          <TooltipValue>{status.replace(/_/g, ' ')}</TooltipValue> —{' '}
          {STATUS_MEANING[status] ?? 'Status not recognised.'}
        </>
      }
    >
      <span
        className={cn(
        // `relative` anchors the pulse's glow pseudo-element; it is inert
        // otherwise.
          'relative inline-flex w-fit shrink-0 items-center whitespace-nowrap rounded-[4px] border bg-transparent px-[9px] py-[3px] font-mono text-[10.5px] leading-none tracking-[0.08em] uppercase',
          pulsing && 'status-pulse',
          className,
        )}
        // Inline rather than Tailwind classes so this reads from STATUS_TOKEN
        // like every other consumer. A class map would be a second copy of the
        // same mapping, and the two would drift the first time a status was
        // added. The border keeps its previous 50% strength via color-mix.
        style={
          {
            color,
            borderColor: `color-mix(in srgb, ${color} 50%, transparent)`,
            // Read by .status-pulse::after — the flash is the colour just
            // arrived at.
            '--status-glow': `color-mix(in srgb, ${color} 45%, transparent)`,
          } as CSSProperties
        }
        onAnimationEnd={onAnimationEnd}
      >
        {status.replace(/_/g, ' ')}
      </span>
    </Tooltip>
  )
}
