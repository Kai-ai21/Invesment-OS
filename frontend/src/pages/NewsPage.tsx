import { useMemo } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'

import { NewsList } from '@/components/news/NewsList'
import { Button } from '@/components/ui/button'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useNews } from '@/hooks/useNews'

const ALL = '__all__'

/** The address for a filter state. `/news` is the unfiltered feed. */
function filterHref(ticker: string): string {
  return ticker === ALL ? '/news' : `/news?ticker=${encodeURIComponent(ticker)}`
}

export function NewsPage() {
  useDocumentTitle('News')
  const { items, loading, error, refreshing, refresh, reload } = useNews()
  const [searchParams] = useSearchParams()

  // ⚠️ THE URL IS THE FILTER STATE, not a useState mirrored into it. That is what
  // makes /news?ticker=NVDA a real address: linkable, bookmarkable, and walked by
  // the back button. Uppercased so a hand-typed ?ticker=nvda still matches.
  const requested = searchParams.get('ticker')?.trim().toUpperCase()
  const activeTicker = requested || ALL

  // Derived from what was already fetched — the filter never triggers a request.
  const tickers = useMemo(() => {
    const distinct = new Set(items.map((item) => item.ticker))
    // A ticker asked for in the URL keeps its chip even with nothing behind it.
    // Without this, a link to a ticker the feed has no headlines for renders an
    // empty list with no chip selected, which reads as a broken page rather than
    // as an answer. The empty message below names the ticker for the same reason —
    // it replaces an older silent fall-back to "All", which quietly showed
    // everything to someone who had asked for one thing.
    if (activeTicker !== ALL) distinct.add(activeTicker)
    return [...distinct].sort()
  }, [items, activeTicker])

  const visible = useMemo(
    () =>
      activeTicker === ALL
        ? items
        : items.filter((item) => item.ticker === activeTicker),
    [items, activeTicker],
  )

  return (
    <div>
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl tracking-[0.01em] text-text-primary">
            News
          </h1>
          {refreshing && (
            <span className="flex items-center gap-1.5 text-xs text-text-secondary">
              <Loader2 className="size-3 animate-spin" aria-hidden />
              Updating…
            </span>
          )}
        </div>
        <Button variant="outline" onClick={refresh} disabled={refreshing}>
          <RefreshCw aria-hidden />
          Refresh
        </Button>
      </header>

      {tickers.length > 0 && (
        // A <nav> rather than a group of buttons: every chip is now a destination.
        <nav
          aria-label="Filter by ticker"
          className="mb-6 flex flex-wrap items-center gap-2"
        >
          <FilterChip label="All" ticker={ALL} selected={activeTicker === ALL} />
          {tickers.map((option) => (
            <FilterChip
              key={option}
              label={option}
              ticker={option}
              selected={activeTicker === option}
            />
          ))}
        </nav>
      )}

      <NewsList
        items={visible}
        loading={loading}
        error={error}
        onRetry={reload}
        emptyMessage={
          activeTicker === ALL
            ? 'No recent news for your tickers.'
            : `No recent news for ${activeTicker}.`
        }
      />
    </div>
  )
}

/**
 * A LINK wearing the button's styling, not a button. Same appearance and same
 * click, but it can also be middle-clicked, copied, or opened in a new tab —
 * which is the point of the filter living in the URL. `aria-current` replaces the
 * old `aria-pressed`: this no longer toggles anything, it navigates.
 */
function FilterChip({
  label,
  ticker,
  selected,
}: {
  label: string
  ticker: string
  selected: boolean
}) {
  return (
    <Button
      asChild
      size="sm"
      variant={selected ? 'secondary' : 'ghost'}
      className={selected ? 'font-mono' : 'font-mono text-text-secondary'}
    >
      <Link to={filterHref(ticker)} aria-current={selected ? 'page' : undefined}>
        {label}
      </Link>
    </Button>
  )
}
