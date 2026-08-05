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
 * The same status colour as a WASH to lay over a surface, e.g. the thesis card's
 * header zone.
 *
 * ⚠️ TRANSLUCENT, NOT PRE-MIXED WITH A BACKGROUND. It mixes the status colour with
 * `transparent`, so it composites over whatever is beneath it — which is what lets
 * the thesis card keep its hover lift: the fill underneath brightens by one step
 * and the tint rides on top unchanged. Mixing against a hard-coded surface colour
 * instead would freeze the tint to one background and kill the hover.
 *
 * ⚠️ THE DEFAULT IS 8% AND IT IS A CEILING, NOT A STARTING POINT. These sit ten to
 * a list. At 8% over the inset surface a red card is about #1c1317 — enough to
 * sort a column by eye, not enough to read as an alert. `--status-pending` is the
 * neutral grey, so an unscored thesis tints to nothing in particular for free.
 *
 * Note this follows STATUS, never price direction: green here means "the claims
 * are holding up", the same as it means everywhere else in the app. See the
 * warning on Sparkline for the other half of that rule.
 */
export function statusTint(status: string | null | undefined, percent = 8): string {
  return `color-mix(in srgb, ${statusColor(status)} ${percent}%, transparent)`
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
 *
 * ⚠️ THE BOX IS RESERVED, because a badge changes size for two different reasons
 * and both used to move the page.
 *
 * HEIGHT is now fixed at `h-5` (20px), the same as the `ui/badge` primitive. It
 * was previously 21px, derived from `py-1` plus an 11px line — and that single
 * pixel is why a market card carrying a status badge measured 178px while one
 * carrying a plain "Track this" link measured 173px, giving the grid two
 * different row heights.
 *
 * WIDTH gets a floor. Measured across the whole vocabulary the labels run from
 * 63px ("BROKEN") to 153px ("STRONGLY SUPPORTED") — a 90px spread — so a claim
 * re-scoring from broken to supported used to resize its badge mid-row and
 * re-wrap the statement beside it. `min-w-24` (96px) covers every thesis status
 * and every verdict, so those never move. STRONGLY SUPPORTED still exceeds it:
 * padding a 153px floor onto every badge in the app would cost more space than
 * the jitter it prevents, so that one case is absorbed by the row instead — see
 * the fixed-width badge column on ClaimCard, which is where it actually mattered.
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
          'relative inline-flex h-5 w-fit min-w-24 shrink-0 items-center justify-center whitespace-nowrap rounded-xs border bg-transparent px-2 font-mono text-2xs leading-none tracking-[0.08em] uppercase',
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
