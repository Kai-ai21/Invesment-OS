import { useCallback, useEffect, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  error: Error | null
  loading: boolean
  reload: () => void
}

/**
 * Run an async loader and expose loading/error/data plus a retry.
 *
 * `load` is a dependency of the effect, so callers must wrap it in `useCallback`
 * — otherwise every render refetches.
 */
export function useAsync<T>(load: () => Promise<T>): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)

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

  return { data, error, loading, reload }
}
