import { useCallback, useState, type ReactNode } from 'react'
import {
  ArrowLeft,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Loader2,
  NotebookPen,
  X,
} from 'lucide-react'
import { Link, useParams } from 'react-router'

import { CompanyLogo } from '@/components/CompanyLogo'
import { Count } from '@/components/Count'
import { RelativeTime } from '@/components/RelativeTime'
import { TickerNewsSection } from '@/components/news/TickerNewsSection'
import { ErrorState } from '@/components/ErrorState'
import { StatusBadge } from '@/components/StatusBadge'
import { ClaimScoreBar } from '@/components/thesis/ClaimScoreBar'
import { ThesisHoldingLine } from '@/components/portfolio/ThesisHoldingLine'
import { ThesisReflections } from '@/components/reflection/ThesisReflections'
import { AddDocumentPanel } from '@/components/thesis/AddDocumentPanel'
import { PriceChart } from '@/components/thesis/PriceChart'
import { CheckNowControls, CheckNowResult } from '@/components/thesis/CheckNow'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/components/ui/toast'
import { Tooltip, TooltipValue, TruncatedText } from '@/components/ui/tooltip'
import { useAsync } from '@/hooks/useAsync'
import { useCheckNow } from '@/hooks/useCheckNow'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useShellContext } from '@/hooks/useShellContext'
import {
  ApiError,
  createManualPostMortem,
  getThesis,
  listEvidence,
  type Claim,
  type EvidenceEvent,
  type Thesis,
} from '@/lib/api'
import { describeError } from '@/lib/errors'
import { formatConfidence, timestamp } from '@/lib/format'
import { cn } from '@/lib/utils'

interface DetailData {
  thesis: Thesis
  evidence: EvidenceEvent[]
}

export function ThesisDetailPage() {
  const { id } = useParams<{ id: string }>()

  const load = useCallback(async (): Promise<DetailData> => {
    if (!id) throw new ApiError(404, '', '/theses')
    // Sequential on purpose: if the thesis is missing, the evidence call would
    // 404 too and we'd rather surface the first, clearer failure.
    const thesis = await getThesis(id)
    const evidence = await listEvidence(id)
    return { thesis, evidence }
  }, [id])

  const { data, error, loading, refreshing, reload, refresh } = useAsync<DetailData>(load)
  // Declared before the early returns — hooks can't be conditional. The trigger
  // renders in the header while the summary renders below it, which is why this
  // state lives here rather than inside one component.
  // Bumped to remount ThesisReflections so it refetches. A key bump rather than
  // lifting the fetch: the reflections block owns its own loading/error states and
  // there is no reason for the page to duplicate them.
  const [reflectionsKey, setReflectionsKey] = useState(0)
  // Which claim the evidence list is narrowed to, or null for all of it. Lives
  // here because the claims and the evidence are two sibling sections.
  const [filterClaimId, setFilterClaimId] = useState<string | null>(null)

  // Refresh the thesis AND re-read its reflections. Both a check and a document
  // submission can break a claim, which opens a post-mortem server-side — refreshing
  // only the thesis left that post-mortem invisible until a manual page reload.
  const refreshAll = useCallback(async () => {
    try {
      await refresh()
    } finally {
      // In `finally` on purpose: the post-mortem may exist even when refreshing the
      // thesis itself failed, so the reflections must still be re-read.
      setReflectionsKey((key) => key + 1)
    }
  }, [refresh])

  const check = useCheckNow(id, refreshAll)
  // Null until the thesis loads — the id in the URL is a uuid, which would be a
  // worse tab label than the plain app name. Distinct from the research page's
  // "NVDA" so the two are told apart in history.
  useDocumentTitle(data ? `${data.thesis.ticker} thesis` : null)

  if (loading) return <DetailSkeleton />
  if (error) {
    return error instanceof ApiError && error.status === 404 ? (
      <NotFoundState />
    ) : (
      <DetailErrorState error={error} onRetry={reload} />
    )
  }
  if (!data) return <NotFoundState />

  const { thesis, evidence } = data
  const newestFirst = [...evidence].sort(
    (a, b) => timestamp(b.created_at) - timestamp(a.created_at),
  )

  // A filter pointing at a claim that no longer exists would silently show an
  // empty list, so it falls back to showing everything.
  const filteredClaim =
    thesis.claims.find((claim) => claim.id === filterClaimId) ?? null
  const visibleEvidence = filteredClaim
    ? newestFirst.filter((event) => event.claim_id === filteredClaim.id)
    : newestFirst

  return (
    <div>
      <BackLink />

      {/* Sticky, so the ticker and its status stay visible while reading down the
          evidence list — which is why it gets the glass treatment. The negative
          margins bleed it to the container edges so content passes underneath
          the blur rather than beside it. */}
      {/* `min-h-22` is the box the skeleton reserves. Pinning it here too means the
          header is one fixed height whether or not ThesisHoldingLine has anything
          to render — that line arrives on its own request, and without this it
          grew the header under the reader a second after the page painted. */}
      <header className="glass-chrome sticky top-0 z-10 -mx-12 mt-6 mb-6 flex min-h-22 flex-wrap items-start justify-between gap-4 border-b px-12 py-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Detail-page ticker in the display font (weight 400). The list-card
              tickers stay on the sans — display font is for titles, not data rows. */}
          <CompanyLogo ticker={thesis.ticker} logoUrl={thesis.logo_url} size={40} />
          <h1 className="font-display text-3xl tracking-[0.01em] text-text-primary">
            {thesis.ticker}
          </h1>
          <StatusBadge status={thesis.status} />
          {/* Secondary, not muted: #6b7280 measures 2.9:1 against the glass
              panel, below AA-large. The secondary tone clears AA at 5.4:1.
              Everything below the header sits on flat cards and keeps muted. */}
          {refreshing && (
            <span className="flex items-center gap-1.5 text-xs text-text-secondary">
              <Loader2 className="size-3 animate-spin" aria-hidden />
              Updating…
            </span>
          )}

          {/* What you own of this ticker, if anything. Facts only, and absent
              entirely when there is no holding — see ThesisHoldingLine. */}
          <ThesisHoldingLine ticker={thesis.ticker} />
        </div>

        <div className="flex flex-col items-end gap-1.5">
          <div className="flex items-center gap-3">
            <RelativeTime
              iso={thesis.created_at}
              prefix="Created"
              className="text-sm text-text-secondary"
            />
            {/* The company behind the thesis, in its own words. */}
            <Button asChild variant="ghost" size="sm">
              <Link to={`/research/${encodeURIComponent(thesis.ticker)}`}>
                <BookOpen aria-hidden />
                Research
              </Link>
            </Button>
            <ReflectButton
              thesisId={thesis.id}
              onCreated={() => setReflectionsKey((key) => key + 1)}
            />
            <CheckNowControls check={check} />
          </div>
          <p className="text-xs text-text-secondary">
            Each filing costs one AI call per claim.
          </p>
        </div>
      </header>

      {/* Near the top on purpose: a thesis that just broke is the moment reflection
          matters, and burying it under the evidence would make it a chore. It is
          never blocking — the card carries its own "Skip for now". */}
      <ThesisReflections key={reflectionsKey} thesisId={thesis.id} />

      {/* Below the header: the price line is the canvas, the evidence and status
          markers on it are the point. */}
      <PriceChart thesisId={thesis.id} />

      <div className="mb-12 flex flex-col gap-4">
        <CheckNowResult check={check} />
        <AddDocumentPanel thesisId={thesis.id} onSubmitted={refreshAll} />
      </div>

      <section className="mb-12">
        <SectionHeading>Original reasoning</SectionHeading>
        {/* Original reasoning is prose too — same serif family as the statements. */}
        <blockquote className="border-l-2 border-border pl-4 font-serif text-base leading-relaxed whitespace-pre-wrap text-text-secondary">
          {thesis.reasoning_raw}
        </blockquote>
      </section>

      <section className="mb-12">
        <SectionHeading>
          Claims
          <Count value={thesis.claims.length} />
        </SectionHeading>
        {thesis.claims.length === 0 ? (
          <p className="text-sm text-text-secondary">No claims were extracted.</p>
        ) : (
          <ul className="flex flex-col gap-4">
            {thesis.claims.map((claim) => (
              <li key={claim.id}>
                <ClaimCard
                  claim={claim}
                  filtered={filteredClaim?.id === claim.id}
                  onFilter={setFilterClaimId}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <SectionHeading>
          Evidence
          {/* "N of M" while a claim filter is on, so the number in the heading is
              never at odds with the number of rows underneath it. */}
          {filteredClaim && newestFirst.length > 0 ? (
            <>
              {' '}
              <span className="font-normal tabular-nums text-text-muted">
                ({visibleEvidence.length} of {newestFirst.length})
              </span>
            </>
          ) : (
            <Count value={newestFirst.length} />
          )}
        </SectionHeading>

        {/* The filter is set from a claim card further up the page, which may be
            scrolled out of sight by the time the reader reaches the list — so the
            list says what it is showing and offers its own way out. */}
        {filteredClaim && (
          <div
            role="status"
            className="mb-4 flex flex-wrap items-center gap-x-2 gap-y-1.5 rounded-lg bg-surface-raised px-4 py-2.5 text-sm"
          >
            <span className="shrink-0 text-text-secondary">
              Showing evidence for one claim:
            </span>
            {/* TRUNCATED, not wrapped. This banner is a single status line above a
                list, and interpolating a claim of unknown length into it made its
                height depend on which claim you filtered by — so the whole evidence
                list below jumped as you switched between them. TruncatedText only
                attaches the tooltip when it measures as actually clipped. */}
            <TruncatedText
              text={`“${filteredClaim.statement}”`}
              className="min-w-0 flex-1 font-serif text-text-primary"
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setFilterClaimId(null)}
              className="ml-auto shrink-0 text-text-secondary hover:text-text-primary"
            >
              <X aria-hidden />
              Show all
            </Button>
          </div>
        )}

        {visibleEvidence.length === 0 ? (
          <p className="text-sm text-text-secondary">No evidence yet.</p>
        ) : (
          <ul className="flex flex-col gap-4">
            {visibleEvidence.map((event) => (
              <li key={event.id}>
                <EvidenceCard event={event} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ⚠️ AFTER the evidence log, and deliberately unlike it. The cards above are
          quoted from a document, scored against a claim and badged with a verdict;
          these are headlines nobody has checked. Adjacent on the page is exactly
          where they would be mistaken for each other, so this section keeps its own
          heading, its own note, and flat rows with no badges on them. */}
      <TickerNewsSection
        ticker={thesis.ticker}
        limit={5}
        moreHref={`/research/${encodeURIComponent(thesis.ticker)}`}
        moreLabel="Company research"
        className="mt-12"
      />
    </div>
  )
}

function ReflectButton({
  thesisId,
  onCreated,
}: {
  thesisId: string
  onCreated: () => void
}) {
  const { refreshPendingReflections } = useShellContext()
  const toast = useToast()
  const [pending, setPending] = useState(false)

  async function handleClick() {
    if (pending) return
    setPending(true)
    try {
      await createManualPostMortem(thesisId)
      onCreated()
      void refreshPendingReflections()
      toast.success('Reflection opened — find it below')
    } catch (cause: unknown) {
      // Was an inline message INSIDE the page header, which grew the header and
      // shifted the whole page down the moment it appeared.
      toast.error(
        `Couldn't open a reflection. ${describeError(cause, 'this reflection').detail}`,
      )
    } finally {
      setPending(false)
    }
  }

  return (
    // Available at ANY status, not just breaking — rethinking a thesis is useful
    // long before it falls apart.
    <Tooltip content="Open a reflection on this thesis">
      <Button
        variant="ghost"
        size="sm"
        onClick={handleClick}
        disabled={pending}
        className="text-text-secondary hover:text-text-primary"
      >
        {pending ? (
          <Loader2 className="animate-spin" aria-hidden />
        ) : (
          <NotebookPen aria-hidden />
        )}
        Reflect
      </Button>
    </Tooltip>
  )
}


function ClaimCard({
  claim,
  filtered,
  onFilter,
}: {
  claim: Claim
  /** True when the evidence list below is currently narrowed to this claim. */
  filtered: boolean
  onFilter: (claimId: string | null) => void
}) {
  const [openConditions, setOpenConditions] = useState(false)
  const conditionsId = `conditions-${claim.id}`

  return (
    <Card>
      <div className="flex flex-col gap-3 px-(--card-spacing)">
        <div className="flex items-start justify-between gap-4">
          {/* Claim statement is prose — serif, ~16px, weight 400, comfortable leading. */}
          <p className="font-serif text-base leading-[1.5] text-text-primary">
            {claim.statement}
          </p>
          {/* ⚠️ THE BADGE COLUMN IS A FIXED WIDTH. This is the one place the
              badge's 63px–153px range changed more than itself: it sits beside a
              wrapping serif statement, so a claim re-scoring from BROKEN to
              STRONGLY SUPPORTED took 90px away from the paragraph, re-flowed it
              onto an extra line and grew the card. `min-w-40` (160px) clears the
              widest label, so the statement's measure is constant. */}
          <div className="flex shrink-0 items-center justify-end gap-2">
            <span className="min-w-12 rounded-full bg-surface-raised px-2 py-0.5 text-center text-xs text-text-muted">
              {claim.is_core ? 'core' : 'minor'}
            </span>
            <StatusBadge status={claim.status} className="min-w-40" />
          </div>
        </div>

        {/* The engine's working, on one line: what it scored, where that sits,
            and how much it was judged on. */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <ClaimScoreBar
            score={claim.score}
            scale={claim.score_scale}
            status={claim.status}
          />

          <EvidenceFilterButton claim={claim} active={filtered} onToggle={onFilter} />

          {/* ⚠️ COLLAPSED BY DEFAULT. Proof and break conditions are the contract
              the claim is judged against — reference material you consult when a
              status surprises you, not something you scan a list of claims for.
              Always-open, they tripled every card's height and pushed the actual
              evidence off the screen. */}
          <button
            type="button"
            onClick={() => setOpenConditions((open) => !open)}
            aria-expanded={openConditions}
            aria-controls={conditionsId}
            className="ml-auto flex items-center gap-1 rounded-lg text-xs text-text-muted transition-colors hover:text-text-secondary focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            {openConditions ? (
              <ChevronDown className="size-3.5" aria-hidden />
            ) : (
              <ChevronRight className="size-3.5" aria-hidden />
            )}
            Conditions
          </button>
        </div>

        {openConditions && (
          <dl id={conditionsId} className="grid gap-3 border-t border-border pt-3 sm:grid-cols-2">
            <Condition label="Proof condition" value={claim.proof_condition} />
            <Condition label="Break condition" value={claim.break_condition} />
          </dl>
        )}
      </div>
    </Card>
  )
}

/**
 * The claim's evidence count, as the control that filters the list below to it.
 *
 * A count with nothing behind it is a dead end — the reader's next question after
 * "four events" is always "which four". Zero is NOT a button: there is nothing to
 * filter to, and a control that does nothing when pressed is worse than plain text.
 */
function EvidenceFilterButton({
  claim,
  active,
  onToggle,
}: {
  claim: Claim
  active: boolean
  onToggle: (claimId: string | null) => void
}) {
  const label = `${claim.evidence_count} evidence ${claim.evidence_count === 1 ? 'event' : 'events'}`

  if (claim.evidence_count === 0) {
    return <span className="text-xs text-text-muted">no evidence yet</span>
  }

  return (
    <Tooltip
      content={
        active
          ? 'Showing only this claim’s evidence. Click to show all again.'
          : 'Show only this claim’s evidence below'
      }
    >
      <button
        type="button"
        onClick={() => onToggle(active ? null : claim.id)}
        aria-pressed={active}
        className={cn(
          'rounded-full border px-2 py-0.5 text-xs tabular-nums transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
          active
            ? 'border-border-strong bg-surface-raised text-text-primary'
            : 'border-transparent text-text-muted hover:border-border hover:text-text-secondary',
        )}
      >
        {label}
      </button>
    </Tooltip>
  )
}

function Condition({ label, value }: { label: string; value: string }) {
  return (
    <div>
      {/* Label stays small uppercase muted sans; the VALUE goes mono (a spec/rule),
          ~12.5px, a touch tighter than the serif statements. */}
      <dt className="text-xs tracking-wide text-text-muted uppercase">{label}</dt>
      <dd className="mt-1 font-mono text-xs leading-[1.4] text-text-secondary">
        {value}
      </dd>
    </div>
  )
}

function EvidenceCard({ event }: { event: EvidenceEvent }) {
  return (
    <Card>
      <div className="flex flex-col gap-3 px-(--card-spacing)">
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={event.verdict} />
          {/* The badge rounds to whole percent for scanning; the score behind it
              is what the claim's status was actually computed from, and two
              events that both read "83%" can carry different weight. The tooltip
              is where that unrounded number lives. */}
          <Tooltip
            content={
              <>
                Raw score <TooltipValue>{event.confidence.toFixed(4)}</TooltipValue> —
                how strongly this evidence counts toward the claim's status.
              </>
            }
          >
            <span className="cursor-help font-mono text-xs tabular-nums text-text-muted underline decoration-dotted decoration-text-muted/40 underline-offset-4">
              {formatConfidence(event.confidence)} confidence
            </span>
          </Tooltip>
          <RelativeTime iso={event.created_at} className="ml-auto text-xs text-text-muted" />
        </div>

        <blockquote className="border-l-2 border-border pl-4 text-sm leading-relaxed text-text-secondary italic">
          {event.evidence_quote}
        </blockquote>

        <p className="text-sm leading-relaxed text-text-secondary">{event.reasoning}</p>
      </div>
    </Card>
  )
}

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-4 font-heading text-sm font-medium tracking-wide text-text-primary uppercase">
      {children}
    </h2>
  )
}

function BackLink() {
  return (
    <Link
      to="/theses"
      className="flex w-fit items-center gap-1.5 rounded-lg text-sm text-text-secondary transition-colors hover:text-text-primary focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <ArrowLeft className="size-4" aria-hidden />
      All theses
    </Link>
  )
}

/**
 * ⚠️ THE HEADER IS THE PART THAT HAS TO BE EXACT.
 *
 * A detail page cannot predict how tall its body will be — the claim count and the
 * evidence log are whatever the thesis has — so matching the whole page is not on
 * offer. What IS predictable is everything above the first card, and that is what
 * the reader is looking at when the data lands. The loaded header is a 40px logo
 * and a 30px title inside `py-4`, measuring 87px, with `mt-6 mb-6` around it; the
 * skeleton now reserves the same box instead of the 36px row it used to, which was
 * pulling the entire page up by 51px at the moment it painted.
 */
function DetailSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading thesis">
      <Skeleton className="h-5 w-24" />
      <div className="-mx-12 mt-6 mb-6 flex min-h-22 items-center gap-3 border-b border-border px-12 py-4">
        <Skeleton className="size-10 rounded-lg" />
        <Skeleton className="h-8 w-28" />
        <Skeleton className="h-5 w-24 rounded-xs" />
      </div>
      <Skeleton className="mb-12 h-20 w-full" />
      <div className="flex flex-col gap-4">
        {[0, 1].map((i) => (
          <Skeleton key={i} className="h-32 w-full rounded-xl" />
        ))}
      </div>
    </div>
  )
}

function NotFoundState() {
  return (
    <div>
      <BackLink />
      <Card className="mt-6 [--card-spacing:--spacing(12)]">
        <div className="flex flex-col items-center gap-4 px-(--card-spacing) text-center">
          <div>
            <p className="font-heading text-base font-medium text-text-primary">
              Thesis not found
            </p>
            <p className="mt-1 text-sm text-text-secondary">
              It may have been deleted, or the link is wrong.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/theses">Back to theses</Link>
          </Button>
        </div>
      </Card>
    </div>
  )
}

function DetailErrorState({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  return (
    <div>
      <BackLink />
      <ErrorState
        error={error}
        subject="this thesis"
        onRetry={onRetry}
        className="mt-6"
      />
    </div>
  )
}
