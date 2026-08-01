import type { CSSProperties } from 'react'

import { cn } from '@/lib/utils'

/** Per-item offset, and the item after which everything shares one delay. */
export const STAGGER_STEP_MS = 40
export const STAGGER_MAX_STEPS = 8
/** Matches the .stagger-in duration in index.css. */
export const STAGGER_DURATION_MS = 320

/**
 * When the last row has finished, plus a margin. useStaggerIndex stops handing
 * out indices at this point, which takes the class off every row — safe only
 * because by then the animation has ended, and its final frame IS the element's
 * natural state, so removing it changes nothing on screen.
 */
export const STAGGER_TOTAL_MS =
  STAGGER_STEP_MS * STAGGER_MAX_STEPS + STAGGER_DURATION_MS + 120

/** How far into the sequence a given row sits. */
export function staggerDelayMs(index: number): number {
  return Math.min(index, STAGGER_MAX_STEPS) * STAGGER_STEP_MS
}

/**
 * Entry animation for one row of a list: fade up, offset by its position.
 *
 * ⚠️ WHY THE CAP. Without it the delay grows with the list, so the twentieth row
 * of a portfolio waits 800ms and the page reads as slow rather than as arriving.
 * Past `STAGGER_MAX_STEPS` every remaining row shares the last delay and comes in
 * together — the sequence is a flourish on the first handful, not a queue.
 *
 * `index: undefined` opts out entirely. That is how a list stops staggering once
 * it has played (see useStaggerIndex), and how the same components render outside
 * a staggered list.
 */
export function entryProps(
  index: number | undefined,
  className?: string,
): { className?: string; style?: CSSProperties } {
  if (index === undefined) return { className }

  return {
    className: cn('stagger-in', className),
    style: { animationDelay: `${staggerDelayMs(index)}ms` },
  }
}
