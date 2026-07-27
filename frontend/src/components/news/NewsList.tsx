import { RefreshCw } from 'lucide-react'

import { NewsItem } from '@/components/news/NewsItem'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { NewsItem as NewsItemData } from '@/lib/api'

/**
 * Every rendering state for a list of headlines, in ONE place: loading, error,
 * empty, loaded. The panel and the /news page both render this, so neither owns
 * any list markup — they only decide which items to hand over.
 */
export function NewsList({
  items,
  loading,
  error,
  onRetry,
  emptyMessage = 'No recent news for your tickers.',
}: {
  items: NewsItemData[]
  loading: boolean
  error: Error | null
  onRetry: () => void
  /** Overridden when a client-side filter is active, so "nothing matches this
   *  filter" doesn't read as "the feed is empty". */
  emptyMessage?: string
}) {
  if (loading) return <NewsSkeleton />
  if (error) return <ErrorState message={error.message} onRetry={onRetry} />
  if (items.length === 0) {
    return <p className="py-6 text-sm text-text-secondary">{emptyMessage}</p>
  }

  return (
    <div className="flex flex-col">
      {items.map((item) => (
        // Feeds can repeat a URL across tickers, so the ticker is part of the key.
        <NewsItem key={`${item.ticker}:${item.url}`} item={item} />
      ))}
    </div>
  )
}

function NewsSkeleton() {
  return (
    <div className="flex flex-col" aria-busy="true" aria-label="Loading news">
      {[0, 1, 2, 3, 4].map((row) => (
        <div
          key={row}
          className="flex flex-col gap-2 border-b border-border py-3 last:border-b-0"
        >
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-2/3" />
          <div className="flex items-center gap-2">
            {/* Matches CompanyLogo's 16px box in the loaded row. */}
            <Skeleton className="size-4 rounded-lg" />
            <Skeleton className="h-4 w-14 rounded-[4px]" />
            <Skeleton className="h-3 w-24" />
          </div>
        </div>
      ))}
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-start gap-3 py-6" role="alert">
      <div>
        <p className="text-sm font-medium text-text-primary">Couldn't load news</p>
        <p className="mt-1 text-sm text-status-broken">{message}</p>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry}>
        <RefreshCw aria-hidden />
        Retry
      </Button>
    </div>
  )
}
