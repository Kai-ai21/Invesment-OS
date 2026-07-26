import { useMemo, useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'

import { NewsList } from '@/components/news/NewsList'
import { Button } from '@/components/ui/button'
import { useNews } from '@/hooks/useNews'

const ALL = '__all__'

export function NewsPage() {
  const { items, loading, error, refreshing, refresh, reload } = useNews()
  const [ticker, setTicker] = useState<string>(ALL)

  // Derived from what was already fetched — the filter never triggers a request.
  const tickers = useMemo(
    () => [...new Set(items.map((item) => item.ticker))].sort(),
    [items],
  )
  const visible = useMemo(
    () => (ticker === ALL ? items : items.filter((item) => item.ticker === ticker)),
    [items, ticker],
  )

  // A selected ticker that vanished after a refresh would silently show nothing.
  const activeTicker = ticker !== ALL && !tickers.includes(ticker) ? ALL : ticker

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
        <div
          role="group"
          aria-label="Filter by ticker"
          className="mb-6 flex flex-wrap items-center gap-2"
        >
          <FilterChip
            label="All"
            selected={activeTicker === ALL}
            onSelect={() => setTicker(ALL)}
          />
          {tickers.map((option) => (
            <FilterChip
              key={option}
              label={option}
              selected={activeTicker === option}
              onSelect={() => setTicker(option)}
            />
          ))}
        </div>
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

function FilterChip({
  label,
  selected,
  onSelect,
}: {
  label: string
  selected: boolean
  onSelect: () => void
}) {
  return (
    <Button
      size="sm"
      variant={selected ? 'secondary' : 'ghost'}
      aria-pressed={selected}
      onClick={onSelect}
      className={selected ? 'font-mono' : 'font-mono text-text-secondary'}
    >
      {label}
    </Button>
  )
}
