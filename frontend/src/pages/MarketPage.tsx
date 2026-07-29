import { useCallback, useMemo, useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'

import { MarketCard } from '@/components/market/MarketCard'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAsync } from '@/hooks/useAsync'
import {
  listHoldings,
  listMarketLeaders,
  listTheses,
  type Holding,
  type Quote,
  type Thesis,
} from '@/lib/api'

interface MarketData {
  quotes: Quote[]
  /** Ticker -> the user's thesis. Empty when that fetch failed; see below. */
  thesesByTicker: Map<string, Thesis>
  holdingsByTicker: Map<string, Holding>
}

export function MarketPage() {
  const load = useCallback(async (): Promise<MarketData> => {
    // The quotes ARE the page, so a failure here is the page's failure.
    const quotes = await listMarketLeaders()

    // The user's own theses and holdings are an OVERLAY on it. A failure in either
    // costs the badges, not the grid, so each degrades to empty rather than taking
    // down eleven perfectly good cards.
    const [theses, portfolio] = await Promise.all([
      listTheses().catch(() => [] as Thesis[]),
      listHoldings().catch(() => null),
    ])

    // Newest thesis wins where a ticker has several — it is the current thinking,
    // and showing an old one's status against a live price would mislead.
    const thesesByTicker = new Map<string, Thesis>()
    for (const thesis of [...theses].sort(
      (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at),
    )) {
      if (!thesesByTicker.has(thesis.ticker)) thesesByTicker.set(thesis.ticker, thesis)
    }

    const holdingsByTicker = new Map<string, Holding>()
    for (const holding of portfolio?.holdings ?? []) {
      if (!holdingsByTicker.has(holding.ticker)) {
        holdingsByTicker.set(holding.ticker, holding)
      }
    }

    return { quotes, thesesByTicker, holdingsByTicker }
  }, [])

  const { data, error, loading, refreshing, reload, refresh } = useAsync<MarketData>(load)
  const [refreshError, setRefreshError] = useState<string | null>(null)

  const handleRefresh = useCallback(async () => {
    setRefreshError(null)
    try {
      await refresh()
    } catch (cause: unknown) {
      // Keeps the current grid on screen and says the refresh failed, rather than
      // replacing good data with a full-page error.
      setRefreshError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [refresh])

  const cards = useMemo(() => data?.quotes ?? [], [data])

  return (
    <div>
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl tracking-[0.01em] text-text-primary">
            Market
          </h1>
          {refreshing && (
            <span className="flex items-center gap-1.5 text-xs text-text-secondary">
              <Loader2 className="size-3 animate-spin" aria-hidden />
              Updating…
            </span>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing || loading}>
          <RefreshCw aria-hidden />
          Refresh
        </Button>
      </header>

      {refreshError && (
        <p role="alert" className="mb-4 text-sm text-status-broken">
          Couldn't refresh: {refreshError}
        </p>
      )}

      {loading ? (
        <MarketSkeleton />
      ) : error ? (
        <ErrorState message={error.message} onRetry={reload} />
      ) : cards.length === 0 ? (
        // Only reachable if the curated list itself were emptied — not a state the
        // user can cause, but the page should not render as a blank rectangle.
        <EmptyState />
      ) : (
        <>
          <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {cards.map((quote) => (
              <li key={quote.ticker} className="h-full">
                <MarketCard
                  quote={quote}
                  thesis={data?.thesesByTicker.get(quote.ticker) ?? null}
                  holding={data?.holdingsByTicker.get(quote.ticker) ?? null}
                />
              </li>
            ))}
          </ul>
          <Provenance />
        </>
      )}
    </div>
  )
}

/**
 * Says which half of this page is maintained by hand. Which twelve companies appear
 * is curated and can go stale without anything noticing; the prices and the order
 * are live. Leaving that unsaid would let the list read as self-maintaining.
 */
function Provenance() {
  return (
    <p className="mt-6 text-xs text-text-muted">
      Membership reviewed manually; prices are live.
    </p>
  )
}

function MarketSkeleton() {
  return (
    <ul
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
      aria-busy="true"
      aria-label="Loading market data"
    >
      {Array.from({ length: 12 }, (_, index) => (
        <li key={index}>
          <Card className="[--card-spacing:--spacing(5)]">
            <div className="flex flex-col gap-3 px-(--card-spacing)">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  {/* Matches CompanyLogo's 32px box so cards don't jump on load. */}
                  <Skeleton className="size-8 rounded-lg" />
                  <div className="flex flex-col gap-1.5">
                    <Skeleton className="h-3.5 w-14" />
                    <Skeleton className="h-3 w-24" />
                  </div>
                </div>
                <Skeleton className="h-8 w-16" />
              </div>
              <Skeleton className="h-6 w-40" />
              <Skeleton className="h-5 w-24 rounded-4xl" />
            </div>
          </Card>
        </li>
      ))}
    </ul>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card className="[--card-spacing:--spacing(6)]">
      <div className="flex flex-col items-start gap-4 px-(--card-spacing)">
        <div>
          <p className="text-sm font-medium text-text-primary">
            Couldn't load market data
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
          No companies to show
        </p>
        <p className="max-w-sm text-sm text-text-secondary">
          The tracked company list is empty.
        </p>
      </div>
    </Card>
  )
}
