import { useCallback } from 'react'

import { useAsync } from '@/hooks/useAsync'
import { getNewsForTicker, listNews, type NewsItem } from '@/lib/api'

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
  return useNewsState(load)
}

/**
 * The same, for ONE ticker — the research page and the thesis detail page read this.
 *
 * A separate hook rather than an argument on useNews: that one is the portfolio's
 * merged feed and every caller wants exactly that, so an optional ticker would make
 * both call sites read as "maybe filtered". They share everything below.
 */
export function useTickerNews(ticker: string, limit = 8): NewsState {
  const load = useCallback(() => getNewsForTicker(ticker, limit), [ticker, limit])
  return useNewsState(load)
}

/** Everything the two hooks have in common — only the loader differs. */
function useNewsState(load: () => Promise<NewsItem[]>): NewsState {
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
