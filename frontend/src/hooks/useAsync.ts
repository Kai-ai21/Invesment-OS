import { useCallback, useEffect, useRef, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  error: Error | null
  loading: boolean
  /** True during a quiet `refresh()`, so callers can show a subtle indicator. */
  refreshing: boolean
  /** Full reload: flips `loading`, so the caller falls back to its skeleton. */
  reload: () => void
  /**
   * Revalidate in place, keeping the current data on screen. Used after a
   * mutation so the result message stays visible while statuses update.
   * Rejects on failure — the caller decides how to surface that.
   */
  refresh: () => Promise<void>
}

/**
 * Run an async loader and expose loading/error/data plus retry and revalidate.
 *
 * `load` is a dependency of the effect, so callers must wrap it in `useCallback`
 * — otherwise every render refetches.
 */
export function useAsync<T>(load: () => Promise<T>): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [attempt, setAttempt] = useState(0)

  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    load()
      .then((result) => {
        if (cancelled) return
        setData(result)
        setLoading(false)
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        setError(cause instanceof Error ? cause : new Error(String(cause)))
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [load, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  const refresh = useCallback(async () => {
    setRefreshing(true)
    try {
      const result = await load()
      // A failure here leaves the existing data in place and propagates to the
      // caller, rather than replacing a good page with a full-page error.
      if (mounted.current) setData(result)
    } finally {
      if (mounted.current) setRefreshing(false)
    }
  }, [load])

  return { data, error, loading, refreshing, reload, refresh }
}
