import { Info } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { useCountUp } from '@/hooks/useCountUp'
import type { PortfolioTotals } from '@/lib/api'
import {
  formatMoney,
  formatSignedMoney,
  formatSignedPercent,
  signOf,
} from '@/lib/format'
import { cn } from '@/lib/utils'

/**
 * The three totals, plus — when it applies — a plain statement of what they leave out.
 *
 * The exclusion notice is not a footnote. A portfolio total that silently omits a
 * position reads as complete and is wrong by however much that position is worth, so
 * it sits directly under the figures it qualifies.
 */
export function PortfolioSummary({ totals }: { totals: PortfolioTotals }) {
  const excluded = totals.holdings_excluded

  // Swept up from zero on the first load only — see useCountUp for the rules,
  // including the two that matter most here: an unavailable figure is never
  // animated, and a loss counts DOWN from zero rather than up out of itself.
  const marketValue = useCountUp(totals.market_value)
  const costBasis = useCountUp(totals.cost_basis)
  const unrealisedPnl = useCountUp(totals.unrealised_pnl)
  const pnlPercent = useCountUp(totals.pnl_percent)

  return (
    <Card className="mb-8 [--card-spacing:--spacing(6)]">
      <div className="flex flex-col gap-5 px-(--card-spacing)">
        <dl className="grid grid-cols-1 gap-5 sm:grid-cols-3">
          <Figure label="Market value" value={formatMoney(marketValue)} />
          <Figure label="Cost basis" value={formatMoney(costBasis)} />
          <Figure
            label="Unrealised P&L"
            value={formatSignedMoney(unrealisedPnl)}
            // Omitted entirely rather than rendered as a dash when there is no
            // percentage (an empty portfolio, or a zero cost basis): "$0.00 —"
            // reads as a broken figure, where "$0.00" alone is simply the truth.
            // The row-level cells still spell unavailability out, because there
            // the dash sits in a column of numbers and has a column heading.
            //
            // Branches on the SOURCE value, not the animated one, so the decision
            // to show a percentage at all can never depend on a frame of the sweep.
            secondary={
              totals.pnl_percent === null
                ? undefined
                : formatSignedPercent(pnlPercent)
            }
            // Likewise the colour: taken from the settled figure so a sweep
            // through zero cannot flicker red and green on the way past.
            tone={signOf(totals.unrealised_pnl)}
          />
        </dl>

        {excluded > 0 && (
          // role="status": the count changes when a refetch resolves, and a total
          // quietly becoming partial is exactly the change worth announcing.
          <p
            role="status"
            className="flex items-start gap-2 border-t border-border pt-4 text-sm text-text-secondary"
          >
            <Info className="mt-0.5 size-4 shrink-0 text-status-weakening" aria-hidden />
            <span>
              <span className="text-text-primary">
                {excluded} {excluded === 1 ? 'holding' : 'holdings'} not included
              </span>{' '}
              — {excluded === 1 ? 'price' : 'prices'} unavailable. These totals cover{' '}
              {totals.holdings_counted}{' '}
              {totals.holdings_counted === 1 ? 'holding' : 'holdings'}.
            </span>
          </p>
        )}
      </div>
    </Card>
  )
}

function Figure({
  label,
  value,
  secondary,
  tone,
}: {
  label: string
  value: string
  secondary?: string
  tone?: 'positive' | 'negative' | null
}) {
  return (
    <div>
      <dt className="font-mono text-[11px] tracking-[0.08em] text-text-muted uppercase">
        {label}
      </dt>
      {/* Mono and tabular so the three figures line up digit-for-digit. */}
      <dd
        className={cn(
          'mt-1.5 font-mono text-2xl tabular-nums',
          tone === 'positive'
            ? 'text-status-strengthening'
            : tone === 'negative'
              ? 'text-status-broken'
              : 'text-text-primary',
        )}
      >
        {value}
        {secondary && (
          // The sign is in the text of both figures, so colour is never the only
          // thing carrying gain-vs-loss.
          <span className="ml-2 align-baseline text-base">{secondary}</span>
        )}
      </dd>
    </div>
  )
}
