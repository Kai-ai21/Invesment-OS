import { useCallback, type ReactNode } from 'react'
import { Plus } from 'lucide-react'
import { Link } from 'react-router'

import { ClaimBreakdown } from '@/components/ClaimBreakdown'
import { CompanyLogo } from '@/components/CompanyLogo'
import { EmptyIllustration } from '@/components/EmptyIllustration'
import { Sparkline } from '@/components/Sparkline'
import { StatusBadge, statusTint } from '@/components/StatusBadge'
import { GLOW_HOST, INSET_CARD, INSET_SURFACE, StatusGlow } from '@/components/StatusSurface'
import { ErrorState } from '@/components/ErrorState'
import { RelativeTime } from '@/components/RelativeTime'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useAsync } from '@/hooks/useAsync'
import { useStaggerIndex } from '@/hooks/useStaggerIndex'
import { listHoldings, listTheses, type Thesis } from '@/lib/api'
import { formatCompactMoney } from '@/lib/format'
import { entryProps } from '@/lib/motion'
import { cn } from '@/lib/utils'

interface ThesesData {
  theses: Thesis[]
  /** Thesis id -> the market value of what the user holds against it. */
  valueByThesis: Map<string, number>
}

export function ThesesPage() {
  useDocumentTitle('Theses')
  const load = useCallback(async (): Promise<ThesesData> => {
    // The theses ARE the page, so a failure here is the page's failure.
    const theses = await listTheses()

    // The portfolio is an OVERLAY on them — same contract as the market grid's
    // badges. Losing it costs one line on some cards, not the list.
    const portfolio = await listHoldings().catch(() => null)
    const valueByThesis = new Map<string, number>()
    for (const holding of portfolio?.holdings ?? []) {
      if (holding.thesis_id === null || holding.market_value === null) continue
      // Summed, not overwritten: one thesis can have several lots against it.
      valueByThesis.set(
        holding.thesis_id,
        (valueByThesis.get(holding.thesis_id) ?? 0) + holding.market_value,
      )
    }

    return { theses, valueByThesis }
  }, [])

  const { data, error, loading, reload } = useAsync<ThesesData>(load)
  const theses = data?.theses
  const staggerIndex = useStaggerIndex(Boolean(theses?.length))

  return (
    <div>
      <header className="mb-8 flex items-center justify-between gap-4">
        <h1 className="font-display text-2xl tracking-[0.01em] text-text-primary">Theses</h1>
        {/* The one gradient pill on the page. The empty-state card below has its
            own "New thesis" button and deliberately keeps the default variant —
            two of these on one screen would leave neither reading as the main
            action. */}
        <Button asChild variant="gradient">
          <Link to="/theses/new">
            <Plus aria-hidden />
            New thesis
          </Link>
        </Button>
      </header>

      {loading ? (
        <ThesesSkeleton />
      ) : error ? (
        <ErrorState error={error} subject="your theses" onRetry={reload} />
      ) : theses && theses.length > 0 ? (
        <ul className="flex flex-col gap-4">
          {theses.map((thesis, index) => (
            <li key={thesis.id} {...entryProps(staggerIndex(index))}>
              <ThesisCard
                thesis={thesis}
                holdingValue={data?.valueByThesis.get(thesis.id) ?? null}
              />
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState />
      )}
    </div>
  )
}

/**
 * One row of the list.
 *
 * ⚠️ TWO ZONES, AND THE SPLIT IS THE WHOLE DESIGN — a HEADER carrying identity and
 * status, and a STATS STRIP carrying the numbers, divided by a hairline. The top
 * carries the only two things worth scanning for (the ticker at 20px and its
 * status) and nothing else competes with them for size or colour; the strip below
 * turns four figures into four labelled columns you can read across a list rather
 * than a run-on sentence you have to parse per card. If a third zone is ever
 * tempting, it belongs on the detail page instead.
 *
 * ⚠️ THE HEIGHT BUDGET IS THE HARD CONSTRAINT, because this is a LIST ROW and not
 * a hero card. Header 56px + hairline + strip 48px lands within a pixel or two of
 * the flat two-tier row this replaced, and every value here (py-3 above, py-2.5
 * below, `leading-none` on both lines of a stat) exists to hold that. A stats
 * strip that reads well alone will happily eat 80px; ten of those is a different
 * page.
 */
function ThesisCard({
  thesis,
  holdingValue,
}: {
  thesis: Thesis
  /** Market value of the user's position, or null when they hold none. */
  holdingValue: number | null
}) {
  const claimCount = thesis.claims.length
  const { evidence_count: evidenceCount, last_evidence_at: lastChecked } = thesis

  // Each entry is a KEY plus a RENDER FUNCTION rather than a bare node. The key
  // makes a stat a stable identity rather than a position, so the fourth column
  // swapping between HELD and AGE does not re-key the three before it; the thunk
  // keeps JSX out of the array literal, where a linter reads it as a list needing
  // keys — which these are not, the key lives on the wrapper.
  const stats: Array<{ key: string; label: string; render: () => ReactNode }> = [
    {
      key: 'claims',
      label: 'Claims',
      render: () => claimCount,
    },
    {
      key: 'evidence',
      label: 'Evidence',
      render: () => evidenceCount,
    },
    // Derived from the newest evidence event, because that IS the last time
    // anything was read against this thesis. Said in a word when it has never
    // happened — a dash here would read as "no data" rather than "not yet done".
    {
      key: 'checked',
      label: 'Checked',
      render: () =>
        lastChecked ? (
          <RelativeTime iso={lastChecked} compact />
        ) : (
          <span className="text-text-muted">never</span>
        ),
    },
    // ⚠️ ONE SLOT, TWO STATS, and the position wins it whenever there is one.
    // Four columns is the most this width holds at a legible size, and money at
    // risk is a better use of the fourth than the date the thesis was typed up.
    //
    // formatCompactMoney only abbreviates from $1M up, so an ordinary position
    // renders in full ("$24,500.00") and is the widest thing the strip ever has
    // to hold. It fits at every width the sidebar leaves for this list; below
    // that it ellipses rather than overflowing (see the cell below). Teaching the
    // shared formatter a thousands scale would fix the width here and change what
    // the market cards print, which is not this change's call to make.
    holdingValue === null
      ? {
          key: 'created',
          label: 'Age',
          render: () => <RelativeTime iso={thesis.created_at} compact />,
        }
      : {
          key: 'held',
          label: 'Held',
          render: () => formatCompactMoney(holdingValue),
        },
  ]

  return (
    <Link
      to={`/theses/${thesis.id}`}
      className="block rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      {/* GLOW_HOST carries the three things the corner bloom needs (see there);
          the Card's own overflow-hidden clips it — and the two zones'
          backgrounds — to the rounded corners. INSET_CARD carries the double
          border and the two-speed brightening of its hover; the fill's own hover
          lift is kept from the raised design, rebased to stay inside the well
          (see --surface-inset-hover).

          ⚠️ `py-0 gap-0` UNDOES THE CARD PRIMITIVE'S OWN PADDING, which is the
          price of full-bleed zones: a tinted band that stops 24px short of the
          card's edges is a rectangle sitting on a card, not a zone of it. Each
          zone pays its own padding back, and the horizontal 24px is still the
          shared --card-spacing so identity lines up with every other card. */}
      <Card
        className={cn(
          'gap-0 bg-surface-inset py-0 hover:bg-surface-inset-hover',
          GLOW_HOST,
          INSET_CARD,
        )}
      >
        {/* Under the header zone's tint, which is 8% and lets it through almost
            untouched — the two are the same colour saying the same thing at two
            scales. */}
        <StatusGlow status={thesis.status} />

        {/* HEADER ZONE.
            ⚠️ NOTHING HERE MAY SHRINK. The obvious `min-w-0` + `truncate` on
            the identity group collapsed the TICKER to zero width at 560px —
            the badge and the sparkline both hold their size, so the one
            flexible item absorbed every pixel of the squeeze and the single
            most important word on the card disappeared. The group wraps
            instead: the badge drops under the ticker, and the ticker is always
            whole. It is at most five characters; there is nothing to truncate.

            The tint is INLINE rather than a class because it is computed from
            the status token — the same reason StatusBadge sets its colours
            inline. See statusTint for why 8%, and why it composites rather than
            pre-mixes. */}
        <div
          className="flex items-center justify-between gap-3 px-(--card-spacing) py-3"
          style={{ background: statusTint(thesis.status) }}
        >
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <CompanyLogo ticker={thesis.ticker} logoUrl={thesis.logo_url} size={32} />
            <span className="shrink-0 font-heading text-xl font-medium text-text-primary">
              {thesis.ticker}
            </span>
            <StatusBadge status={thesis.status} />
            {/* Sits with the badge rather than in the strip below: it is the
                status broken down, not a metric, and at 64x4 it costs no height
                on a 32px row. */}
            <ClaimBreakdown claims={thesis.claims} />
          </div>
          {/* Thirty days: the same span the price card opens on, and short
              enough that a shape is still readable at 20px tall. */}
          <Sparkline ticker={thesis.ticker} days={30} />
        </div>

        {/* STATS STRIP.
            ⚠️ THE TONE RELATIONSHIP IS FIXED IN ONE DIRECTION: this zone gets a
            flat 1.5% neutral lift and the header gets the status tint on top of
            the same fill, so the header is ALWAYS the lighter of the two, for
            every status including pending. Tinting both, or giving this one a
            tone that only works against some statuses, is how a set of four
            cards stops looking like one design. It cannot go DARKER than the
            header instead — #0a0c10 is already within a couple of L* of the
            floor, which is the same wall the alert list hit (see --surface-inset). */}
        <div className="flex border-t border-border/60 bg-foreground/[0.015] py-2.5">
          {stats.map(({ key, label, render }, index) => (
            <div
              key={key}
              className={cn(
                'flex min-w-0 flex-1 flex-col items-center justify-center gap-1 px-2',
                index > 0 && 'border-l border-border/50',
              )}
            >
              {/* ⚠️ `w-full` IS WHAT MAKES `truncate` WORK. In a column flex box
                  with `items-center` an item sizes to its content, so a span with
                  no width to overflow simply grows — which is how "$24,500.00"
                  escaped the card's right edge at 420px instead of ellipsing.
                  Full-width and centred is the same alignment, with a bound. */}
              <span className="w-full truncate text-center font-mono text-sm leading-none tabular-nums text-text-primary">
                {render()}
              </span>
              <span className="w-full truncate text-center text-2xs leading-none tracking-[0.08em] text-text-muted uppercase">
                {label}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </Link>
  )
}

function ThesesSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading theses">
      {/* Mirrors the loaded card's TWO ZONES down to their padding, not just its
          top one — a skeleton a line shorter than what replaces it makes the
          whole list jump. The hairline is real (`border-t`), not a Skeleton bar,
          for the same reason: it is 1px of the height either way, and the divider
          is structure that does not need to look like it is loading. */}
      {[0, 1, 2].map((i) => (
        // INSET_SURFACE, not just a border: it matches the loaded card's 1px
        // hairline exactly — without it the skeleton was 2px shorter than what
        // replaced it, on every card — and its ring means the list does not
        // acquire a second frame per row at the moment the data lands.
        <Card key={i} className={cn('gap-0 bg-surface-inset py-0', INSET_SURFACE)}>
          <div className="flex items-center justify-between gap-3 px-(--card-spacing) py-3">
            <div className="flex items-center gap-3">
              {/* Matches CompanyLogo's 32px box so the row does not jump. */}
              <Skeleton className="size-8 rounded-lg" />
              <Skeleton className="h-6 w-16" />
              <Skeleton className="h-5 w-24 rounded-full" />
              <Skeleton className="h-1 w-16 rounded-full" />
            </div>
            {/* The sparkline's reserved 64x20 box. */}
            <Skeleton className="h-5 w-16" />
          </div>
          {/* Four columns of value-over-label, at the same 14/4/11 rhythm the
              loaded strip lays out at. */}
          <div className="flex border-t border-border/60 bg-foreground/[0.015] py-2.5">
            {[0, 1, 2, 3].map((cell) => (
              <div
                key={cell}
                className="flex flex-1 flex-col items-center gap-1 px-2"
              >
                {/* 14px then 11px, the two line boxes of a loaded stat. The
                    label is h-[11px] rather than h-3: `text-2xs` is 11px and the
                    nearest rung either way left the skeleton a pixel off the card
                    that replaces it — which is a pixel every row in the list
                    jumps by at the moment the data lands. */}
                <Skeleton className="h-3.5 w-8" />
                <Skeleton className="h-[11px] w-12" />
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  )
}


function EmptyState() {
  return (
    <Card className="[--card-spacing:--spacing(12)]">
      <div className="flex flex-col items-center gap-4 px-(--card-spacing) text-center">
        <EmptyIllustration variant="theses" />
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
