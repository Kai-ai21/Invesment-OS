import { useCallback, useId, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { statusColor } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAsync } from '@/hooks/useAsync'
import { getChartData, type ChartData, type ChartEvent } from '@/lib/api'
import { cn } from '@/lib/utils'

const RANGES = [
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '1Y', days: 365 },
] as const


/** One row of the series: a price, plus any events landing on that date. */
interface Row {
  date: string
  close: number
  events: ChartEvent[]
}

/**
 * Where a date sits along the x axis, 0 (left) to 1 (right). Counting rows rather
 * than looking the date up keeps this correct for a date with no row of its own —
 * a category axis places it at the nearest row, and so does this.
 */
function xPosition(rows: Row[], date: string): number {
  if (rows.length < 2) return 0
  const index = rows.filter((row) => row.date <= date).length - 1
  return Math.min(Math.max(index, 0), rows.length - 1) / (rows.length - 1)
}

/** Entry animation is opt-out for users who asked for less motion. */
function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function PriceChart({ thesisId }: { thesisId: string }) {
  const [days, setDays] = useState<number>(365)

  const load = useCallback(() => getChartData(thesisId, days), [thesisId, days])
  const { data, error, loading, reload } = useAsync<ChartData>(load)

  // Events are attached to the price row that shares their date, so a marker sits on
  // the line rather than floating at an interpolated position. Several events on one
  // date collapse into one row and are rendered stacked, never overlapping.
  const rows: Row[] = useMemo(() => {
    if (!data) return []
    const byDate = new Map<string, ChartEvent[]>()
    for (const event of data.events) {
      byDate.set(event.date, [...(byDate.get(event.date) ?? []), event])
    }
    return data.prices.map((point) => ({
      date: point.date,
      close: point.close,
      events: byDate.get(point.date) ?? [],
    }))
  }, [data])

  const statusChanges = useMemo(
    () => (data?.events ?? []).filter((event) => event.type === 'status_change'),
    [data],
  )

  return (
    <Card className="mb-10 [--card-spacing:--spacing(5)]">
      <div className="flex flex-col gap-4 px-(--card-spacing)">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-base tracking-[0.01em] text-text-primary">
            Price
          </h2>
          <div role="group" aria-label="Chart range" className="flex items-center gap-1">
            {RANGES.map((range) => (
              <Button
                key={range.label}
                size="sm"
                variant={days === range.days ? 'secondary' : 'ghost'}
                aria-pressed={days === range.days}
                onClick={() => setDays(range.days)}
                className={cn('font-mono', days !== range.days && 'text-text-secondary')}
              >
                {range.label}
              </Button>
            ))}
          </div>
        </header>

        {loading ? (
          <Skeleton className="h-64 w-full rounded-lg" />
        ) : error ? (
          <ErrorState message={error.message} onRetry={reload} />
        ) : !data || data.prices.length === 0 ? (
          // Never a flat line at zero — say plainly that there is no price data, and
          // note when the user's own events survived the failure.
          <EmptyState
            unavailable={data?.prices_unavailable ?? false}
            eventCount={data?.events.length ?? 0}
          />
        ) : (
          <ChartBody rows={rows} statusChanges={statusChanges} />
        )}
      </div>
    </Card>
  )
}

function ChartBody({
  rows,
  statusChanges,
}: {
  rows: Row[]
  statusChanges: ChartEvent[]
}) {
  // Two charts can share a page (and SVG ids are document-global), so the gradient
  // ids are per-instance. useId's own delimiters aren't safe inside url(#…), hence
  // the strip.
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '')
  const fillId = `price-fill-${uid}`
  const strokeId = `price-stroke-${uid}`

  return (
    <div className="h-64 w-full">
      {/* ResponsiveContainer so the chart reflows when the sidebar collapses. */}
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <defs>
            {/* VERTICAL — the area fill. Brightest just under the line, gone by the
                baseline, so the fill gives the series weight without becoming a
                block of tone the markers have to fight. */}
            <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.22} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
            </linearGradient>

            {/* HORIZONTAL — the stroke itself, oldest → newest, so recent data reads
                brightest. The left end bottoms out at 0.35, never lower: history is
                de-emphasised, not erased. */}
            <linearGradient id={strokeId} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={1} />
            </linearGradient>
          </defs>

          {/* Grid dimmed and dashed: against the fill, the previous weight read as
              noise crossing the shaded band. */}
          <CartesianGrid
            stroke="var(--border)"
            strokeDasharray="2 5"
            strokeOpacity={0.5}
            vertical={false}
          />
          <XAxis
            dataKey="date"
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: 'var(--border)' }}
            minTickGap={40}
            tickFormatter={(value: string) => value.slice(5)} // MM-DD
          />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={52}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--border)' }} />

          {/* Declared BEFORE the reference lines so the fill sits underneath them —
              recharts paints children in order, and a status line washed out by 22%
              white would lose the colour that identifies which status it marks. */}
          <Area
            type="monotone"
            dataKey="close"
            fill={`url(#${fillId})`}
            stroke={`url(#${strokeId})`}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
            dot={<EventDot />}
            activeDot={{ r: 3, fill: 'var(--text-secondary)' }}
            isAnimationActive={!prefersReducedMotion()}
          />

          {/* Status changes as vertical lines, coloured by the status moved INTO.
              Two things go wrong if the label is just dropped next to the line:
              transitions CLUSTER (a thesis can weaken and break within days) so
              side-by-side labels overlap into mush — hence the staggered rows — and
              they cluster at *now*, which is the right edge, so a right-hand label
              is clipped by the plot. Labels past the 70% mark flip to the left. */}
          {statusChanges.map((event, index) => {
            const flip = xPosition(rows, event.date) > 0.7
            return (
              <ReferenceLine
                key={`${event.date}-${index}`}
                x={event.date}
                stroke={statusColor(event.new_status)}
                strokeDasharray="4 3"
                strokeOpacity={0.8}
                label={{
                  value: `→ ${event.new_status}`,
                  // insideTopRight anchors the text's END at the line, so it runs
                  // leftward into the plot instead of off the edge.
                  position: flip ? 'insideTopRight' : 'insideTopLeft',
                  fill: statusColor(event.new_status),
                  fontSize: 10,
                  // Cycle through rows so neighbouring lines never share one.
                  dy: 4 + (index % 4) * 12,
                  dx: flip ? -4 : 4,
                }}
              />
            )
          })}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

/**
 * Renders a marker only where evidence landed. Contradicting evidence is prominent;
 * supporting evidence is deliberately quieter, because a thesis breaking is the thing
 * worth noticing. Neutral evidence never reaches the frontend.
 */
function EventDot(props: { cx?: number; cy?: number; payload?: Row }) {
  const { cx, cy, payload } = props
  if (cx === undefined || cy === undefined || !payload?.events.length) return null

  const evidence = payload.events.filter((event) => event.type === 'evidence')
  if (evidence.length === 0) return null

  const contradicts = evidence.some((event) => event.verdict === 'contradicts')
  const color = statusColor(contradicts ? 'contradicts' : 'supports')
  const radius = contradicts ? 5 : 3.5

  return (
    <g>
      <circle
        cx={cx}
        cy={cy}
        r={radius}
        fill={color}
        fillOpacity={contradicts ? 1 : 0.55}
        stroke="var(--background)"
        strokeWidth={1.5}
      />
      {/* More than one on a date: a count badge instead of stacked circles nobody
          could tell apart. The tooltip lists them all. */}
      {evidence.length > 1 && (
        <text
          x={cx}
          y={cy - radius - 4}
          textAnchor="middle"
          fontSize={9}
          fill="var(--text-secondary)"
        >
          {evidence.length}
        </text>
      )}
    </g>
  )
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: Row }>
}) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload

  return (
    <div className="max-w-xs rounded-lg border border-border bg-surface-raised p-3 shadow-lg">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-mono text-xs text-text-secondary">{row.date}</span>
        <span className="font-mono text-sm text-text-primary">
          {row.close.toFixed(2)}
        </span>
      </div>

      {row.events.length > 0 && (
        <ul className="mt-2 flex flex-col gap-2 border-t border-border pt-2">
          {row.events.map((event, index) => (
            <li key={index} className="flex flex-col gap-0.5">
              {event.type === 'status_change' ? (
                <span
                  className="font-mono text-[10px] tracking-[0.08em] uppercase"
                  style={{ color: statusColor(event.new_status) }}
                >
                  {event.prev_status} → {event.new_status}
                </span>
              ) : (
                <>
                  <span
                    className="font-mono text-[10px] tracking-[0.08em] uppercase"
                    style={{ color: statusColor(event.verdict) }}
                  >
                    {event.verdict}
                  </span>
                  {event.claim_statement && (
                    <span className="font-serif text-xs leading-snug text-text-primary">
                      {event.claim_statement}
                    </span>
                  )}
                  {event.quote && (
                    <span className="font-serif text-xs leading-snug text-text-secondary italic">
                      “{event.quote}”
                    </span>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function EmptyState({
  unavailable,
  eventCount,
}: {
  unavailable: boolean
  eventCount: number
}) {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-1 text-center">
      <p className="text-sm text-text-primary">
        {unavailable ? 'Price data unavailable' : 'No price data for this ticker'}
      </p>
      <p className="max-w-sm text-sm text-text-secondary">
        {unavailable
          ? eventCount > 0
            ? `The price source could not be reached. Your ${eventCount} recorded ${
                eventCount === 1 ? 'event' : 'events'
              } are unaffected.`
            : 'The price source could not be reached.'
          : 'This ticker returned no closing prices for the selected range.'}
      </p>
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex h-64 flex-col items-start justify-center gap-3" role="alert">
      <div>
        <p className="text-sm font-medium text-text-primary">Couldn't load the chart</p>
        <p className="mt-1 text-sm text-status-broken">{message}</p>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry}>
        <RefreshCw aria-hidden />
        Retry
      </Button>
    </div>
  )
}
