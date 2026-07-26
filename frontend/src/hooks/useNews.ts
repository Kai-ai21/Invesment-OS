import { useCallback } from 'react'

import { useAsync } from '@/hooks/useAsync'
import { listNews, type NewsItem } from '@/lib/api'

export interface NewsState {
  items: NewsItem[]
  loading: boolean
  error: Error | null
  /** True during a quiet refresh, so the header can show a spinner without the
   *  list collapsing back to skeletons. */
  refreshing: boolean
  /** Quiet revalidate — keeps the current list on screen. For the refresh button. */
  refresh: () => void
  /** Full reload, flipping `loading` back to the skeletons. For retry-after-error,
   *  where there is no list to keep. */
  reload: () => void
}

/**
 * The single fetch path for news. Both the slide-over panel and the /news page use
 * this, so neither owns its own request logic.
 */
export function useNews(limitPerTicker = 5): NewsState {
  const load = useCallback(() => listNews(limitPerTicker), [limitPerTicker])
  const { data, error, loading, refreshing, refresh, reload } =
    useAsync<NewsItem[]>(load)

  return {
    // Never null downstream: "no data yet" and "empty feed" both render as a list,
    // and `loading`/`error` already distinguish them.
    items: data ?? [],
    loading,
    error,
    refreshing,
    // useAsync.refresh rejects on failure; the existing list stays on screen and the
    // rejection is swallowed here rather than becoming an unhandled promise.
    refresh: () => void refresh().catch(() => {}),
    reload,
  }
}
