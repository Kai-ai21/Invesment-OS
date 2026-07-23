import { useCallback } from 'react'
import { Plus, RefreshCw } from 'lucide-react'
import { Link } from 'react-router'

import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAsync } from '@/hooks/useAsync'
import { listTheses, type Thesis } from '@/lib/api'
import { formatDate } from '@/lib/format'

export function ThesesPage() {
  const load = useCallback(() => listTheses(), [])
  const { data: theses, error, loading, reload } = useAsync<Thesis[]>(load)

  return (
    <div>
      <header className="mb-8 flex items-center justify-between gap-4">
        <h1 className="font-display text-2xl tracking-[0.01em] text-text-primary">Theses</h1>
        <Button asChild>
          <Link to="/theses/new">
            <Plus aria-hidden />
            New thesis
          </Link>
        </Button>
      </header>

      {loading ? (
        <ThesesSkeleton />
      ) : error ? (
        <ErrorState message={error.message} onRetry={reload} />
      ) : theses && theses.length > 0 ? (
        <ul className="flex flex-col gap-4">
          {theses.map((thesis) => (
            <li key={thesis.id}>
              <ThesisCard thesis={thesis} />
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState />
      )}
    </div>
  )
}

function ThesisCard({ thesis }: { thesis: Thesis }) {
  const claimCount = thesis.claims.length

  return (
    <Link
      to={`/theses/${thesis.id}`}
      className="block rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <Card className="[--card-spacing:--spacing(5)] transition-colors hover:bg-surface-raised">
        <div className="flex items-center justify-between gap-4 px-(--card-spacing)">
          <div className="flex items-center gap-3">
            <span className="font-heading text-xl font-medium text-text-primary">
              {thesis.ticker}
            </span>
            <StatusBadge status={thesis.status} />
          </div>
          <div className="flex shrink-0 items-center gap-4 text-sm text-text-muted">
            <span>
              {claimCount} {claimCount === 1 ? 'claim' : 'claims'}
            </span>
            <span>{formatDate(thesis.created_at)}</span>
          </div>
        </div>
      </Card>
    </Link>
  )
}

function ThesesSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading theses">
      {[0, 1, 2].map((i) => (
        <Card key={i} className="[--card-spacing:--spacing(5)]">
          <div className="flex items-center justify-between gap-4 px-(--card-spacing)">
            <div className="flex items-center gap-3">
              <Skeleton className="h-6 w-16" />
              <Skeleton className="h-5 w-24 rounded-4xl" />
            </div>
            <div className="flex items-center gap-4">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-24" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card className="[--card-spacing:--spacing(6)]">
      <div className="flex flex-col items-start gap-4 px-(--card-spacing)">
        <div>
          <p className="text-sm font-medium text-text-primary">Couldn't load theses</p>
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
      <div className="flex flex-col items-center gap-4 px-(--card-spacing) text-center">
        <div>
          <p className="font-heading text-base font-medium text-text-primary">
            No theses yet
          </p>
          <p className="mt-1 text-sm text-text-secondary">
            Write up your reasoning on a ticker and we'll extract the claims to track.
          </p>
        </div>
        <Button asChild>
          <Link to="/theses/new">
            <Plus aria-hidden />
            New thesis
          </Link>
        </Button>
      </div>
    </Card>
  )
}
