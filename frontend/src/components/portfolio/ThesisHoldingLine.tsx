import { useCallback, useMemo } from 'react'
import { Link } from 'react-router'

import { Skeleton } from '@/components/ui/skeleton'
import { useAsync } from '@/hooks/useAsync'
import { listHoldings, type Portfolio } from '@/lib/api'
import {
  formatMoney,
  formatPercent,
  formatShares,
  formatSignedMoney,
  formatSignedPercent,
  signOf,
} from '@/lib/format'
import { cn } from '@/lib/utils'

/**
 * What the user owns of this ticker, on the thesis page. One quiet line of facts:
 * size, value, share of the portfolio, P&L.
 *
 * ⚠️ FACTS ONLY. It states the position and stops. Sitting next to a status that may
 * read "breaking", the temptation to add a line about what that combination means is
 * exactly the thing this project has refused from the start — the user connects the
 * two, and the app does not do it for them.
 *
 * RENDERS NOTHING when there is no holding for this ticker. Owning nothing is the
 * normal case for most theses, and an empty "you don't own this" line on every page
 * would be noise rather than information.
 */
export function ThesisHoldingLine({ ticker }: { ticker: string }) {
  const load = useCallback(() => listHoldings(), [])
  const { data, error, loading } = useAsync<Portfolio>(load)

  const holding = useMemo(
    () => data?.holdings.find((row) => row.ticker === ticker) ?? null,
    [data, ticker],
  )

  if (loading) return <Skeleton className="h-4 w-64" />

  // Supplementary context, so a failure is stated once and quietly — no retry
  // button competing with the page's own actions, and never a blocking error for
  // something the thesis does not depend on.
  if (error) {
    return <span className="text-xs text-text-muted">Holding unavailable</span>
  }

  if (!holding) return null

  const tone = signOf(holding.unrealised_pnl)

  return (
    <Link
      to="/portfolio"
      className="inline-flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg text-xs focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <Fact label="Shares" value={formatShares(holding.shares)} />
      <Fact label="Value" value={formatMoney(holding.market_value)} />
      <Fact label="Allocation" value={formatPercent(holding.allocation_percent)} />
      <Fact
        label="P&L"
        value={
          holding.unrealised_pnl === null
            ? formatSignedMoney(null)
            : `${formatSignedMoney(holding.unrealised_pnl)} (${formatSignedPercent(holding.pnl_percent)})`
        }
        tone={tone}
      />
    </Link>
  )
}

function Fact({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: 'positive' | 'negative' | null
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span className="text-text-muted">{label}</span>
      <span
        className={cn(
          'font-mono tabular-nums',
          tone === 'positive'
            ? 'text-status-strengthening'
            : tone === 'negative'
              ? 'text-status-broken'
              : 'text-text-secondary',
        )}
      >
        {value}
      </span>
    </span>
  )
}
