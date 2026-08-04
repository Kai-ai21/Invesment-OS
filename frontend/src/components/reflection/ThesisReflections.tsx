import { useCallback, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

import { ReflectionCard } from '@/components/reflection/ReflectionCard'
import { Skeleton } from '@/components/ui/skeleton'
import { usePostMortems } from '@/hooks/usePostMortems'
import { useShellContext } from '@/hooks/useShellContext'

/**
 * The reflections belonging to one thesis, for the detail page: any pending one shown
 * prominently, past answered ones tucked behind a disclosure.
 *
 * Renders NOTHING when there are none — a thesis that has never broken should not
 * carry an empty "Reflections" heading.
 */
export function ThesisReflections({ thesisId }: { thesisId: string }) {
  const { items, loading, error, refresh } = usePostMortems(thesisId)
  const { refreshPendingReflections } = useShellContext()
  const [showPast, setShowPast] = useState(false)

  // Saving or deleting changes the pending count behind the sidebar badge.
  const handleChanged = useCallback(() => {
    refresh()
    void refreshPendingReflections()
  }, [refresh, refreshPendingReflections])

  if (loading) {
    return <Skeleton className="mb-6 h-59 w-full rounded-xl" />
  }
  // A failed reflection fetch must not disturb the thesis itself — the page's real
  // content is the claims and evidence, so this stays quiet rather than showing an
  // error block above them.
  if (error) return null

  const pending = items.filter((item) => item.user_response === null)
  const answered = items.filter((item) => item.user_response !== null)
  if (pending.length === 0 && answered.length === 0) return null

  return (
    // gap-4 throughout, here and in the collapsed list below: a reflection card
    // carries the inset shell, whose outer ring stands 3px proud on every side,
    // and 12px of gap left the rings of two stacked cards 6px apart.
    <section className="mb-12 flex flex-col gap-4">
      {pending.map((item) => (
        <ReflectionCard key={item.id} postMortem={item} onChanged={handleChanged} />
      ))}

      {answered.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowPast((open) => !open)}
            aria-expanded={showPast}
            className="flex items-center gap-1.5 rounded-lg text-sm text-text-secondary transition-colors hover:text-text-primary focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            {showPast ? (
              <ChevronDown className="size-4" aria-hidden />
            ) : (
              <ChevronRight className="size-4" aria-hidden />
            )}
            Past reflections ({answered.length})
          </button>

          {showPast && (
            <div className="mt-4 flex flex-col gap-4">
              {answered.map((item) => (
                <ReflectionCard
                  key={item.id}
                  postMortem={item}
                  onChanged={handleChanged}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
