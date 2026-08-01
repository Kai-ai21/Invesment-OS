import { useCallback } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'

import { EmptyIllustration } from '@/components/EmptyIllustration'
import { PatternsSection } from '@/components/pattern/PatternsSection'
import { ReflectionCard } from '@/components/reflection/ReflectionCard'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { sortReflections, usePostMortems } from '@/hooks/usePostMortems'
import { useShellContext } from '@/hooks/useShellContext'
import { useStaggerIndex } from '@/hooks/useStaggerIndex'

export function ReflectionsPage() {
  const { items, loading, error, refreshing, refresh, reload } = usePostMortems()
  const { refreshPendingReflections } = useShellContext()

  const handleChanged = useCallback(() => {
    refresh()
    void refreshPendingReflections()
  }, [refresh, refreshPendingReflections])

  const ordered = sortReflections(items)
  const staggerIndex = useStaggerIndex(ordered.length > 0)

  return (
    <div>
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl tracking-[0.01em] text-text-primary">
            Reflections
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

      {/* Patterns sit ABOVE the reflections: they are the payoff, and the
          reflections below are the raw material they were drawn from. */}
      <PatternsSection postMortems={items} loadingPostMortems={loading} />

      <h2 className="mb-4 font-display text-xl tracking-[0.01em] text-text-primary">
        Your reflections
      </h2>

      {loading ? (
        <ReflectionsSkeleton />
      ) : error ? (
        <ErrorState message={error.message} onRetry={reload} />
      ) : ordered.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="flex flex-col gap-4">
          {ordered.map((item, index) => (
            <ReflectionCard
              key={item.id}
              postMortem={item}
              onChanged={handleChanged}
              index={staggerIndex(index)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ReflectionsSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading reflections">
      {[0, 1].map((row) => (
        <Skeleton key={row} className="h-56 w-full rounded-xl" />
      ))}
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card className="[--card-spacing:--spacing(6)]">
      <div className="flex flex-col items-start gap-4 px-(--card-spacing)">
        <div>
          <p className="text-sm font-medium text-text-primary">
            Couldn't load reflections
          </p>
          <p className="mt-1 text-sm text-status-broken">{message}</p>
        </div>
        <Button variant="outline" onClick={onRetry}>
          <RefreshCw aria-hidden />
          Retry
        </Button>
      </div>
    </Card>
  )
}

function EmptyState() {
  return (
    <Card className="[--card-spacing:--spacing(10)]">
      <div className="flex flex-col items-center gap-1 px-(--card-spacing) text-center">
        <EmptyIllustration variant="reflections" className="mb-3" />
        <p className="font-display text-base tracking-[0.01em] text-text-primary">
          No reflections yet
        </p>
        <p className="text-sm text-text-secondary">
          When a thesis breaks, you'll be asked what you missed.
        </p>
      </div>
    </Card>
  )
}
