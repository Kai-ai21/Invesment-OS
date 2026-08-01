import { useCallback } from 'react'
import { Plus, RefreshCw } from 'lucide-react'
import { Link } from 'react-router'

import { ClaimBreakdown } from '@/components/ClaimBreakdown'
import { CompanyLogo } from '@/components/CompanyLogo'
import { EmptyIllustration } from '@/components/EmptyIllustration'
import { Sparkline } from '@/components/Sparkline'
import { StatusBadge } from '@/components/StatusBadge'
import { StatusSpine } from '@/components/StatusSpine'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAsync } from '@/hooks/useAsync'
import { useStaggerIndex } from '@/hooks/useStaggerIndex'
import { listHoldings, listTheses, type Thesis } from '@/lib/api'
import { formatDate, formatMoney, formatRelative } from '@/lib/format'
import { entryProps } from '@/lib/motion'

interface ThesesData {
  theses: Thesis[]
  /** Thesis id -> the market value of what the user holds against it. */
  valueByThesis: Map<string, number>
}

export function ThesesPage() {
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
        <ErrorState message={error.message} onRetry={reload} />
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
 * ⚠️ TWO TIERS, AND THE SPLIT IS THE WHOLE DESIGN. The top line carries the only
 * two things worth scanning for — the ticker, at 20px, and its status — and
 * nothing else competes with them for size or colour. Everything added below is
 * one line of 12px muted text plus a 1px bar: enough to answer "is this worth
 * opening" without turning a list into a page of dashboards. If a third tier is
 * ever tempting, it belongs on the detail page instead.
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

  return (
    <Link
      to={`/theses/${thesis.id}`}
      className="block rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      {/* `relative` so the spine can pin to the edge; the Card's own
          overflow-hidden clips it to the rounded corners. The hairline uses the
          border token and brightens on hover — the spine does not, because it
          carries meaning rather than interaction state. */}
      <Card className="relative border border-border [--card-spacing:--spacing(5)] transition-colors hover:border-border-strong hover:bg-surface-raised">
        <StatusSpine status={thesis.status} />
        <div className="flex flex-col gap-2.5 px-(--card-spacing)">
          {/* PRIMARY.
              ⚠️ NOTHING HERE MAY SHRINK. The obvious `min-w-0` + `truncate` on
              the identity group collapsed the TICKER to zero width at 560px —
              the badge and the sparkline both hold their size, so the one
              flexible item absorbed every pixel of the squeeze and the single
              most important word on the card disappeared. The group wraps
              instead: the badge drops under the ticker, and the ticker is always
              whole. It is at most five characters; there is nothing to truncate. */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
              <CompanyLogo ticker={thesis.ticker} logoUrl={thesis.logo_url} size={32} />
              <span className="shrink-0 font-heading text-xl font-medium text-text-primary">
                {thesis.ticker}
              </span>
              <StatusBadge status={thesis.status} />
            </div>
            {/* Thirty days: the same span the price card opens on, and short
                enough that a shape is still readable at 20px tall. */}
            <Sparkline ticker={thesis.ticker} days={30} />
          </div>

          {/* SECONDARY — one wrapping line, all of it 12px and muted. */}
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-text-muted">
            <ClaimBreakdown claims={thesis.claims} />
            {/* Each entry is a KEY plus its text, rather than bare nodes in an
                array: the keys are then stable identities rather than positions,
                so the holding line appearing does not re-key everything after it. */}
            {(
              [
                ['claims', `${claimCount} ${claimCount === 1 ? 'claim' : 'claims'}`],
                [
                  'evidence',
                  `${evidenceCount} evidence ${evidenceCount === 1 ? 'event' : 'events'}`,
                ],
                // Derived from the newest evidence event, because that IS the last
                // time anything was read against this thesis. Said plainly when it
                // has never happened — "checked never" would be worse than useless.
                [
                  'checked',
                  lastChecked ? `checked ${formatRelative(lastChecked)}` : 'never checked',
                ],
                // The one figure on the line, so it goes mono and one step brighter
                // — it is a number to read, not a label to skim.
                holdingValue === null
                  ? null
                  : ['held', `${formatMoney(holdingValue)} held`, 'money'],
                ['created', formatDate(thesis.created_at)],
              ] as Array<[string, string, string?] | null>
            )
              .filter((item) => item !== null)
              .map(([key, text, tone], index) => (
                // Each separator lives INSIDE the item it precedes, so a wrap
                // carries the two together and no line ever ends on a stray dot.
                <span key={key} className="flex items-center gap-2.5 whitespace-nowrap">
                  {index > 0 && <Dot />}
                  <span
                    className={
                      tone === 'money'
                        ? 'font-mono tabular-nums text-text-secondary'
                        : undefined
                    }
                  >
                    {text}
                  </span>
                </span>
              ))}
          </div>
        </div>
      </Card>
    </Link>
  )
}

/** Separator between metadata items. Hidden from screen readers, which get the
 *  items as separate elements already. */
function Dot() {
  return (
    <span aria-hidden className="text-text-muted/40">
      ·
    </span>
  )
}

function ThesesSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading theses">
      {/* Mirrors the loaded card's TWO tiers, not just its top one — a skeleton
          a line shorter than what replaces it makes the whole list jump. */}
      {[0, 1, 2].map((i) => (
        <Card key={i} className="[--card-spacing:--spacing(5)]">
          <div className="flex flex-col gap-2.5 px-(--card-spacing)">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                {/* Matches CompanyLogo's 32px box so the row does not jump. */}
                <Skeleton className="size-8 rounded-lg" />
                <Skeleton className="h-6 w-16" />
                <Skeleton className="h-5 w-24 rounded-4xl" />
              </div>
              {/* The sparkline's reserved 64x20 box. */}
              <Skeleton className="h-5 w-16" />
            </div>
            <div className="flex items-center gap-2.5">
              <Skeleton className="h-1 w-16 rounded-full" />
              <Skeleton className="h-3 w-14" />
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-3 w-28" />
              <Skeleton className="h-3 w-20" />
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
