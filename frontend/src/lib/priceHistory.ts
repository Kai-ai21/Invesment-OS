import { getPriceHistory, type PriceHistory } from '@/lib/api'

/**
 * Matches HISTORY_TTL_SECONDS in backend/services/price_service.py. Daily closes
 * change once a session, so holding them for the same six hours the server does
 * keeps the two from disagreeing about how stale is stale.
 */
const TTL_MS = 6 * 60 * 60 * 1000

interface Entry {
  at: number
  /** Null is a real answer — this ticker has no history and never will today. */
  value: PriceHistory | null
}

const settled = new Map<string, Entry>()
const inFlight = new Map<string, Promise<PriceHistory | null>>()

/** Distinct spans are distinct series; a 30-day cache cannot serve a 90-day ask. */
function keyFor(ticker: string, days: number): string {
  return `${ticker.trim().toUpperCase()}:${days}`
}

/** Drop everything. For tests. */
export function clearPriceHistoryCache(): void {
  settled.clear()
  inFlight.clear()
}

/**
 * Daily closes for a ticker, fetched at most once per ticker per span.
 *
 * ⚠️ WHY THIS EXISTS ON TOP OF THE SERVER CACHE. The server's cache is real and
 * it works — measured on twelve market tickers, a cold pass costs 1.9s of
 * upstream calls and a warm pass 0.02s, so roughly a hundredfold. What it cannot
 * do is stop the BROWSER asking. A ticker can appear three times on one screen
 * (a market card, a thesis card, a portfolio row) and every mount would issue its
 * own request for a series the page already has.
 *
 * So this layer answers two different questions:
 *   - `inFlight` collapses concurrent asks for the same series into ONE request,
 *     which is the case that actually bites, because a list mounts all its rows
 *     in the same tick.
 *   - `settled` stops a remount — navigating away and back — refetching a series
 *     that has not changed.
 *
 * A 404 (no history for this ticker) is cached as null, exactly as the server
 * caches an unknown ticker: it is an answer, not a failure. Genuine failures are
 * NOT cached, so one blip does not blank a sparkline for six hours.
 */
export function loadPriceHistory(
  ticker: string,
  days: number,
): Promise<PriceHistory | null> {
  const key = keyFor(ticker, days)

  const cached = settled.get(key)
  if (cached && Date.now() - cached.at < TTL_MS) {
    return Promise.resolve(cached.value)
  }

  const pending = inFlight.get(key)
  if (pending) return pending

  const request = getPriceHistory(ticker, days)
    .then((history) => {
      settled.set(key, { at: Date.now(), value: history })
      return history
    })
    .catch((cause: unknown) => {
      // 404 is "this ticker has no history", which is a settled fact worth
      // remembering. Anything else is a failure and stays uncached.
      const status = (cause as { status?: number })?.status
      if (status === 404) {
        settled.set(key, { at: Date.now(), value: null })
        return null
      }
      throw cause
    })
    .finally(() => {
      inFlight.delete(key)
    })

  inFlight.set(key, request)
  return request
}
