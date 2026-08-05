import { useCallback, useState } from 'react'
import { Check, Loader2 } from 'lucide-react'
import { Link } from 'react-router'

import { EmptyIllustration } from '@/components/EmptyIllustration'
import { RelativeTime } from '@/components/RelativeTime'
import { StatusBadge } from '@/components/StatusBadge'
import { GLOW_HOST, INSET_CARD, INSET_SURFACE, StatusGlow } from '@/components/StatusSurface'
import { ErrorState } from '@/components/ErrorState'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/components/ui/toast'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useAsync } from '@/hooks/useAsync'
import { useShellContext } from '@/hooks/useShellContext'
import { useStaggerIndex } from '@/hooks/useStaggerIndex'
import { listAlerts, markAlertRead, type Alert } from '@/lib/api'
import { describeError } from '@/lib/errors'

import { entryProps } from '@/lib/motion'
import { cn } from '@/lib/utils'

type Filter = 'all' | 'unread'

export function AlertsPage() {
  useDocumentTitle('Alerts')
  const { refreshUnreadCount } = useShellContext()
  const toast = useToast()
  const [filter, setFilter] = useState<Filter>('all')

  const load = useCallback(() => listAlerts(filter === 'unread'), [filter])
  const { data: alerts, setData, error, loading, reload } = useAsync<Alert[]>(load)
  const staggerIndex = useStaggerIndex(Boolean(alerts?.length))

  // Ids currently being marked read — doubles as the double-click guard.
  const [marking, setMarking] = useState<ReadonlySet<string>>(new Set())

  async function handleMarkRead(id: string) {
    if (marking.has(id)) return
    setMarking((prev) => new Set(prev).add(id))

    try {
      const updated = await markAlertRead(id)
      // Swap the row in place rather than refetching: the response is the new
      // state, and under the "unread" filter a refetch would make the card
      // vanish out from under the click.
      setData((prev) =>
        prev ? prev.map((a) => (a.id === updated.id ? updated : a)) : prev,
      )
      await refreshUnreadCount()
      toast.success(`${updated.ticker} alert marked as read`)
    } catch (cause: unknown) {
      // Was a banner above the list, which pushed every card down the page on
      // appearing and pulled them back up on the next attempt. Nothing here needs
      // studying — the row is still there and the button still works.
      toast.error(`Couldn't mark as read. ${describeError(cause, 'this alert').detail}`)
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

      {loading ? (
        <AlertsSkeleton />
      ) : error ? (
        <ErrorState error={error} subject="your alerts" onRetry={reload} />
      ) : alerts && alerts.length > 0 ? (
        /* gap-4, not gap-3, and the ring is the reason: it stands 3px proud of
           each card on every side, so 12px of gap left only 6px of clear page
           between one card's ring and the next one's — close enough that the
           two read as a single seam. 16px leaves 10px. Matched by the skeleton
           below, or the list would resettle when the data landed. */
        <ul className="flex flex-col gap-4">
          {/* The key is the alert id, so marking one read swaps its contents in
              a row that never left the DOM — nothing re-animates. */}
          {alerts.map((alert, index) => (
            <li key={alert.id} {...entryProps(staggerIndex(index))}>
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
        // The left edge used to carry READ/UNREAD as a grey bar. It then carried
        // the thesis status as a spine, which is the more useful signal; the
        // signal is the same now and the corner glow is how every status-bearing
        // card draws it.
        'bg-surface-inset',
        GLOW_HOST,
        INSET_CARD,
        // ⚠️ READ/UNREAD MOVED OFF THE BACKGROUND, and it had to. It used to be
        // #171a21 against #1d212b; on the inset surface the equivalent pair would
        // be #0a0c10 against a step below it, and there is no room below it —
        // the page is only about 5 L* above black, so the darker of the two was
        // indistinguishable on screen. It was built and it did not work.
        //
        // The hairline has room, so it carries the difference now: a read alert
        // dims to half strength, which is the same "recede" in a place you can
        // actually see it. Hover is untouched and takes both to --border-strong.
        alert.is_read && 'border-border/50',
      )}
    >
      {/* Coloured by the status the thesis moved INTO — the alert is about where
          it ended up, not where it came from. */}
      <StatusGlow status={alert.new_status} />
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

          <RelativeTime iso={alert.created_at} className="text-xs text-text-muted" />
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
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading alerts">
      {[0, 1, 2].map((i) => (
        // Matches the loaded alert card: the same inset shell and 1px border, a
        // 24px identity row (text-base beside two 20px badges), a 20px `text-sm`
        // summary line and a 16px `text-xs` timestamp. Every one of these was a
        // step short before.
        <Card key={i} className={cn('bg-surface-inset', INSET_SURFACE)}>
          <div className="flex flex-col gap-2 px-(--card-spacing)">
            <div className="flex items-center gap-2">
              <Skeleton className="h-6 w-14" />
              <Skeleton className="h-5 w-24 rounded-full" />
              <Skeleton className="h-5 w-24 rounded-full" />
            </div>
            {/* The summary line is `text-sm leading-relaxed`, which lays out at
                22.75px — h-6 is the nearest scale step and lands within 1px. */}
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-24" />
          </div>
        </Card>
      ))}
    </div>
  )
}

function EmptyState({ filter }: { filter: Filter }) {
  return (
    <Card className="[--card-spacing:--spacing(12)]">
      <div className="flex flex-col items-center gap-1 px-(--card-spacing) text-center">
        {/* mb-3 rather than a gap on the container: the two lines of copy below
            are a tight pair and must stay tighter to each other than to this. */}
        <EmptyIllustration variant="alerts" className="mb-3" />
        <p className="font-heading text-base font-medium text-text-primary">
          {filter === 'unread' ? 'No unread alerts' : 'No alerts'}
        </p>
        {/* This sentence is the whole point of the empty state — it reframes an
            absence as a result. The mark above it is punctuation, not a
            replacement. */}
        <p className="text-sm text-text-secondary">
          Silence means nothing meaningful has changed.
        </p>
      </div>
    </Card>
  )
}
