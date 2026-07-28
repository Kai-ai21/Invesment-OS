import { useCallback, useMemo, useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'

import { AddHoldingForm } from '@/components/portfolio/AddHoldingForm'
import { HoldingsTable } from '@/components/portfolio/HoldingsTable'
import { PortfolioSummary } from '@/components/portfolio/PortfolioSummary'
import { sortHoldings, type SortMode } from '@/components/portfolio/sortHoldings'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAsync } from '@/hooks/useAsync'
import { listHoldings, type Portfolio } from '@/lib/api'
import { cn } from '@/lib/utils'

export function PortfolioPage() {
  const load = useCallback(() => listHoldings(), [])
  const { data, setData, error, loading, refreshing, reload, refresh } =
    useAsync<Portfolio>(load)

  const [sortMode, setSortMode] = useState<SortMode>('value')

  const sorted = useMemo(
    () => (data ? sortHoldings(data.holdings, sortMode) : []),
    [data, sortMode],
  )

  // Mutations answer with the whole portfolio, so this swaps it in rather than
  // firing a second request for data we were just handed.
  const handlePortfolio = useCallback(
    (portfolio: Portfolio) => setData(portfolio),
    [setData],
  )

  return (
    <div>
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl tracking-[0.01em] text-text-primary">
            Portfolio
          </h1>
          {refreshing && (
            <span className="flex items-center gap-1.5 text-xs text-text-secondary">
              <Loader2 className="size-3 animate-spin" aria-hidden />
              Updating…
            </span>
          )}
        </div>
        {data && data.holdings.length > 0 && (
          <SortToggle mode={sortMode} onChange={setSortMode} />
        )}
      </header>

      {loading ? (
        <PortfolioSkeleton />
      ) : error ? (
        <ErrorState message={error.message} onRetry={reload} />
      ) : data ? (
        <>
          <PortfolioSummary totals={data.totals} />
          <AddHoldingForm onAdded={handlePortfolio} />
          {data.holdings.length === 0 ? (
            <EmptyState />
          ) : (
            <HoldingsTable
              holdings={sorted}
              onPortfolio={handlePortfolio}
              onRefetch={refresh}
            />
          )}
        </>
      ) : (
        <EmptyState />
      )}
    </div>
  )
}

/**
 * Two orderings, and that is the whole feature.
 *
 * ⚠️ "Needs attention" REORDERS. It does not recommend. Putting a large position
 * with a breaking thesis at the top makes the fact impossible to miss; what to do
 * about it is not this app's business and is not stated here or anywhere else in
 * the portfolio view. The description below says what the sort does, in those terms.
 */
function SortToggle({
  mode,
  onChange,
}: {
  mode: SortMode
  onChange: (mode: SortMode) => void
}) {
  const options = [
    { value: 'value' as const, label: 'Largest first', hint: 'Sorted by market value.' },
    {
      value: 'attention' as const,
      label: 'Needs attention',
      hint: 'Holdings with a weakening or breaking thesis first, largest first within those.',
    },
  ]

  return (
    <div className="flex flex-col items-end gap-1.5">
      <div role="group" aria-label="Sort holdings" className="flex items-center gap-1">
        {options.map((option) => (
          <Button
            key={option.value}
            size="sm"
            variant={mode === option.value ? 'secondary' : 'ghost'}
            aria-pressed={mode === option.value}
            onClick={() => onChange(option.value)}
            className={cn(mode !== option.value && 'text-text-secondary')}
          >
            {option.label}
          </Button>
        ))}
      </div>
      <p className="text-xs text-text-muted">
        {options.find((option) => option.value === mode)?.hint}
      </p>
    </div>
  )
}

function PortfolioSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading portfolio">
      <Card className="mb-8 [--card-spacing:--spacing(6)]">
        <div className="grid grid-cols-1 gap-5 px-(--card-spacing) sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i}>
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-2.5 h-8 w-32" />
            </div>
          ))}
        </div>
      </Card>
      <div className="flex flex-col gap-px rounded-xl border border-border p-3">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex items-center gap-3 py-3">
            {/* Matches CompanyLogo's 28px box so rows don't jump on load. */}
            <Skeleton className="size-7 rounded-lg" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-5 w-24 rounded-4xl" />
            <Skeleton className="ml-auto h-4 w-20" />
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-20" />
          </div>
        ))}
      </div>
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card className="[--card-spacing:--spacing(6)]">
      <div className="flex flex-col items-start gap-4 px-(--card-spacing)">
        <div>
          <p className="text-sm font-medium text-text-primary">
            Couldn't load your portfolio
          </p>
          <p className="mt-1 text-sm text-status-broken">{message}</p>
        </div>
        <Button variant="outline" onClick={onRetry}>
          <RefreshCw aria-hidden />
          Retry
        </Button>
      </div>
    </Card>
  )
}

function EmptyState() {
  return (
    <Card className="[--card-spacing:--spacing(10)]">
      <div className="flex flex-col items-center gap-2 px-(--card-spacing) text-center">
        <p className="font-heading text-base font-medium text-text-primary">
          No holdings yet
        </p>
        <p className="max-w-sm text-sm text-text-secondary">
          Add what you own to see it beside your theses.
        </p>
      </div>
    </Card>
  )
}
