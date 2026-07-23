import { useCallback, useState } from 'react'
import { Check, Loader2, RefreshCw } from 'lucide-react'
import { Link } from 'react-router'

import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAsync } from '@/hooks/useAsync'
import { useShellContext } from '@/hooks/useShellContext'
import { listAlerts, markAlertRead, type Alert } from '@/lib/api'
import { formatRelative } from '@/lib/format'
import { cn } from '@/lib/utils'

type Filter = 'all' | 'unread'

export function AlertsPage() {
  const { refreshUnreadCount } = useShellContext()
  const [filter, setFilter] = useState<Filter>('all')

  const load = useCallback(() => listAlerts(filter === 'unread'), [filter])
  const { data: alerts, setData, error, loading, reload } = useAsync<Alert[]>(load)

  // Ids currently being marked read — doubles as the double-click guard.
  const [marking, setMarking] = useState<ReadonlySet<string>>(new Set())
  const [markError, setMarkError] = useState<string | null>(null)

  async function handleMarkRead(id: string) {
    if (marking.has(id)) return
    setMarking((prev) => new Set(prev).add(id))
    setMarkError(null)

    try {
      const updated = await markAlertRead(id)
      // Swap the row in place rather than refetching: the response is the new
      // state, and under the "unread" filter a refetch would make the card
      // vanish out from under the click.
      setData((prev) =>
        prev ? prev.map((a) => (a.id === updated.id ? updated : a)) : prev,
      )
      await refreshUnreadCount()
    } catch (cause: unknown) {
      setMarkError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setMarking((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  return (
    <div>
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <h1 className="font-display text-2xl tracking-[0.01em] text-text-primary">Alerts</h1>
        <FilterToggle value={filter} onChange={setFilter} />
      </header>

      {markError && (
        <p role="alert" className="mb-4 text-sm text-status-broken">
          Couldn't mark as read: {markError}
        </p>
      )}

      {loading ? (
        <AlertsSkeleton />
      ) : error ? (
        <ErrorState message={error.message} onRetry={reload} />
      ) : alerts && alerts.length > 0 ? (
        <ul className="flex flex-col gap-3">
          {alerts.map((alert) => (
            <li key={alert.id}>
              <AlertCard
                alert={alert}
                marking={marking.has(alert.id)}
                onMarkRead={() => void handleMarkRead(alert.id)}
              />
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState filter={filter} />
      )}
    </div>
  )
}

function FilterToggle({
  value,
  onChange,
}: {
  value: Filter
  onChange: (next: Filter) => void
}) {
  const options: Array<{ id: Filter; label: string }> = [
    { id: 'all', label: 'All' },
    { id: 'unread', label: 'Unread only' },
  ]

  return (
    <div role="group" aria-label="Filter alerts" className="flex items-center gap-1">
      {options.map(({ id, label }) => (
        <Button
          key={id}
          size="sm"
          variant={value === id ? 'secondary' : 'ghost'}
          aria-pressed={value === id}
          onClick={() => onChange(id)}
          className={value === id ? undefined : 'text-text-secondary'}
        >
          {label}
        </Button>
      ))}
    </div>
  )
}

function AlertCard({
  alert,
  marking,
  onMarkRead,
}: {
  alert: Alert
  marking: boolean
  onMarkRead: () => void
}) {
  return (
    <Card
      className={cn(
        '[--card-spacing:--spacing(5)] border-l-2 transition-colors',
        alert.is_read
          ? 'border-l-transparent bg-surface'
          : 'border-l-text-secondary bg-surface-raised',
      )}
    >
      <div className="flex items-start justify-between gap-4 px-(--card-spacing)">
        {/* The link wraps only the card body so the button isn't nested inside
            an anchor. */}
        <Link
          to={`/theses/${alert.thesis_id}`}
          className="flex flex-1 flex-col gap-2 rounded-lg focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                'font-heading text-base font-medium',
                alert.is_read ? 'text-text-secondary' : 'text-text-primary',
              )}
            >
              {alert.ticker}
            </span>
            <StatusBadge status={alert.prev_status} />
            <span aria-hidden className="text-text-muted">
              →
            </span>
            <StatusBadge status={alert.new_status} />
            <span className="sr-only">
              changed from {alert.prev_status} to {alert.new_status}
            </span>
          </div>

          <p
            className={cn(
              'text-sm leading-relaxed',
              alert.is_read ? 'text-text-muted' : 'text-text-secondary',
            )}
          >
            {alert.summary}
          </p>

          <span className="text-xs text-text-muted">
            {formatRelative(alert.created_at)}
          </span>
        </Link>

        {!alert.is_read && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onMarkRead}
            disabled={marking}
            className="shrink-0 text-text-muted hover:text-text-primary"
          >
            {marking ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : (
              <Check aria-hidden />
            )}
            Mark as read
          </Button>
        )}
      </div>
    </Card>
  )
}

function AlertsSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading alerts">
      {[0, 1, 2].map((i) => (
        <Card key={i} className="[--card-spacing:--spacing(5)]">
          <div className="flex flex-col gap-2 px-(--card-spacing)">
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-14" />
              <Skeleton className="h-5 w-24 rounded-4xl" />
              <Skeleton className="h-5 w-24 rounded-4xl" />
            </div>
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-24" />
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
          <p className="text-sm font-medium text-text-primary">Couldn't load alerts</p>
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

function EmptyState({ filter }: { filter: Filter }) {
  return (
    <Card className="[--card-spacing:--spacing(10)]">
      <div className="flex flex-col items-center gap-1 px-(--card-spacing) text-center">
        <p className="font-heading text-base font-medium text-text-primary">
          {filter === 'unread' ? 'No unread alerts' : 'No alerts'}
        </p>
        <p className="text-sm text-text-secondary">
          Silence means nothing meaningful has changed.
        </p>
      </div>
    </Card>
  )
}
