import { useCallback } from 'react'

import { useAsync } from '@/hooks/useAsync'
import {
  listPostMortems,
  listPostMortemsForThesis,
  type PostMortem,
} from '@/lib/api'

export interface PostMortemsState {
  items: PostMortem[]
  loading: boolean
  error: Error | null
  refreshing: boolean
  /** Quiet revalidate — keeps the list on screen. Used after save or delete. */
  refresh: () => void
  /** Full reload, back to skeletons. For retry-after-error. */
  reload: () => void
}

/** All post-mortems, or only this thesis's when `thesisId` is given. */
export function usePostMortems(thesisId?: string): PostMortemsState {
  const load = useCallback(
    () => (thesisId ? listPostMortemsForThesis(thesisId) : listPostMortems()),
    [thesisId],
  )
  const { data, error, loading, refreshing, refresh, reload } =
    useAsync<PostMortem[]>(load)

  return {
    items: data ?? [],
    loading,
    error,
    refreshing,
    // useAsync.refresh rejects on failure; the list stays on screen and the
    // rejection is swallowed rather than becoming an unhandled promise.
    refresh: () => void refresh().catch(() => {}),
    reload,
  }
}

/** Pending first, then answered; newest first within each group. */
export function sortReflections(items: PostMortem[]): PostMortem[] {
  return [...items].sort((a, b) => {
    const aPending = a.user_response === null
    const bPending = b.user_response === null
    if (aPending !== bPending) return aPending ? -1 : 1
    return b.created_at.localeCompare(a.created_at)
  })
}
