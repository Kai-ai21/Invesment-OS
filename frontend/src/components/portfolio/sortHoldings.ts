import type { Holding, ThesisStatus } from '@/lib/api'

export type SortMode = 'value' | 'attention'

/**
 * Statuses that pull a holding to the top under "Needs attention".
 *
 * ⚠️ This sorts. It does not advise. Putting a large breaking position first makes
 * the fact visible; what to do about it is the user's call and is never stated
 * anywhere in this feature.
 */
const ATTENTION_STATUSES: ReadonlySet<ThesisStatus> = new Set(['breaking', 'weakening'])

export function needsAttention(holding: Holding): boolean {
  return holding.thesis_status !== null && ATTENTION_STATUSES.has(holding.thesis_status)
}

/**
 * Largest position first.
 *
 * A null market value SINKS rather than sorting as zero. An unpriced holding is not
 * the smallest position in the portfolio — its size is unknown, and ranking it as
 * worthless is the same mistake as rendering it as $0.00. Ties (and the unpriced
 * rows among themselves) fall back to ticker order so the table never reshuffles
 * between renders.
 */
function byValueDesc(a: Holding, b: Holding): number {
  if (a.market_value === null && b.market_value === null) {
    return a.ticker.localeCompare(b.ticker)
  }
  if (a.market_value === null) return 1
  if (b.market_value === null) return -1
  if (a.market_value === b.market_value) return a.ticker.localeCompare(b.ticker)
  return b.market_value - a.market_value
}

/**
 * Returns a new array — never sorts the caller's data in place, which would mutate
 * the fetched portfolio and make the order depend on how many times it rendered.
 *
 * "attention" partitions the value-ordered list rather than re-sorting it, so
 * "largest first" still holds inside each group.
 */
export function sortHoldings(holdings: Holding[], mode: SortMode): Holding[] {
  const byValue = [...holdings].sort(byValueDesc)
  if (mode === 'value') return byValue

  return [
    ...byValue.filter(needsAttention),
    ...byValue.filter((holding) => !needsAttention(holding)),
  ]
}
