import { useCallback, useRef, useState } from 'react'

import { ApiError, runCheck, type CheckResult } from '@/lib/api'

export const DEFAULT_CHECK_LIMIT = 1
export const MAX_CHECK_LIMIT = 3

/**
 * The check endpoint fails in ways the user can act on, so each status gets its
 * own wording: 422 is the backend telling us something concrete (unknown
 * ticker), 502 is SEC being unavailable and worth retrying.
 */
export function describeCheckError(error: Error): string {
  if (!(error instanceof ApiError)) return error.message
  switch (error.status) {
    case 422:
      return error.detail
    case 502:
      return 'SEC is unavailable or rate-limited. Try again shortly.'
    default:
      return `The check failed (HTTP ${error.status}). ${error.detail}`
  }
}

export interface CheckNowState {
  limit: number
  setLimit: (limit: number) => void
  pending: boolean
  result: CheckResult | null
  error: string | null
  /** The check landed but the follow-up refetch didn't, so the page is stale. */
  stale: boolean
  run: () => void
  dismiss: () => void
}

/**
 * Owns the "check now" action. Lives in a hook because the trigger sits in the
 * page header while the result summary renders below it.
 *
 * @param onChecked revalidates the thesis so statuses on screen match the result.
 */
export function useCheckNow(
  thesisId: string | undefined,
  onChecked: () => Promise<void>,
): CheckNowState {
  const [limit, setLimit] = useState(DEFAULT_CHECK_LIMIT)
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState<CheckResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stale, setStale] = useState(false)

  // A ref, not `pending`, so a second click in the same tick still bounces.
  const inFlight = useRef(false)

  const run = useCallback(() => {
    if (inFlight.current || !thesisId) return
    inFlight.current = true
    setPending(true)
    setError(null)
    setResult(null)
    setStale(false)

    void (async () => {
      try {
        const checkResult = await runCheck(thesisId, limit)
        setResult(checkResult)

        // Refetch inside the pending window so the summary and the refreshed
        // statuses land together. A failure here is NOT a failed check — the
        // work was done, we just couldn't re-read it.
        try {
          await onChecked()
        } catch {
          setStale(true)
        }
      } catch (cause: unknown) {
        setError(
          describeCheckError(
            cause instanceof Error ? cause : new Error(String(cause)),
          ),
        )
      } finally {
        inFlight.current = false
        setPending(false)
      }
    })()
  }, [thesisId, limit, onChecked])

  const dismiss = useCallback(() => {
    setResult(null)
    setError(null)
    setStale(false)
  }, [])

  return { limit, setLimit, pending, result, error, stale, run, dismiss }
}
