import { useCallback, useState, type ReactNode } from 'react'
import { ArrowLeft, BookOpen, Loader2, NotebookPen, RefreshCw } from 'lucide-react'
import { Link, useParams } from 'react-router'

import { CompanyLogo } from '@/components/CompanyLogo'
import { StatusBadge } from '@/components/StatusBadge'
import { ThesisHoldingLine } from '@/components/portfolio/ThesisHoldingLine'
import { ThesisReflections } from '@/components/reflection/ThesisReflections'
import { AddDocumentPanel } from '@/components/thesis/AddDocumentPanel'
import { PriceChart } from '@/components/thesis/PriceChart'
import { CheckNowControls, CheckNowResult } from '@/components/thesis/CheckNow'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAsync } from '@/hooks/useAsync'
import { useCheckNow } from '@/hooks/useCheckNow'
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
import { formatConfidence, formatDate, formatDateTime, timestamp } from '@/lib/format'

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

  if (loading) return <DetailSkeleton />
  if (error) {
    return error instanceof ApiError && error.status === 404 ? (
      <NotFoundState />
    ) : (
      <ErrorState message={error.message} onRetry={reload} />
    )
  }
  if (!data) return <NotFoundState />

  const { thesis, evidence } = data
  const newestFirst = [...evidence].sort(
    (a, b) => timestamp(b.created_at) - timestamp(a.created_at),
  )

  return (
    <div>
      <BackLink />

      {/* Sticky, so the ticker and its status stay visible while reading down the
          evidence list — which is why it gets the glass treatment. The negative
          margins bleed it to the container edges so content passes underneath
          the blur rather than beside it. */}
      <header className="glass-chrome sticky top-0 z-10 -mx-10 mt-6 mb-6 flex flex-wrap items-start justify-between gap-4 border-b px-10 py-4">
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
            <span className="text-sm text-text-secondary">
              Created {formatDate(thesis.created_at)}
            </span>
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

      <div className="mb-10 flex flex-col gap-4">
        <CheckNowResult check={check} />
        <AddDocumentPanel thesisId={thesis.id} onSubmitted={refreshAll} />
      </div>

      <section className="mb-10">
        <SectionHeading>Original reasoning</SectionHeading>
        {/* Original reasoning is prose too — same serif family as the statements. */}
        <blockquote className="border-l-2 border-border pl-4 font-serif text-[15px] leading-relaxed whitespace-pre-wrap text-text-secondary">
          {thesis.reasoning_raw}
        </blockquote>
      </section>

      <section className="mb-10">
        <SectionHeading>
          Claims{' '}
          <span className="font-normal text-text-muted">({thesis.claims.length})</span>
        </SectionHeading>
        {thesis.claims.length === 0 ? (
          <p className="text-sm text-text-secondary">No claims were extracted.</p>
        ) : (
          <ul className="flex flex-col gap-4">
            {thesis.claims.map((claim) => (
              <li key={claim.id}>
                <ClaimCard claim={claim} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <SectionHeading>
          Evidence{' '}
          <span className="font-normal text-text-muted">({newestFirst.length})</span>
        </SectionHeading>
        {newestFirst.length === 0 ? (
          <p className="text-sm text-text-secondary">No evidence yet.</p>
        ) : (
          <ul className="flex flex-col gap-4">
            {newestFirst.map((event) => (
              <li key={event.id}>
                <EvidenceCard event={event} />
              </li>
            ))}
          </ul>
        )}
      </section>
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
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleClick() {
    if (pending) return
    setPending(true)
    setError(null)
    try {
      await createManualPostMortem(thesisId)
      onCreated()
      void refreshPendingReflections()
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setPending(false)
    }
  }

  return (
    <span className="flex items-center gap-2">
      {error && (
        <span role="alert" className="text-xs text-status-broken">
          {error}
        </span>
      )}
      {/* Available at ANY status, not just breaking — rethinking a thesis is useful
          long before it falls apart. */}
      <Button
        variant="ghost"
        size="sm"
        onClick={handleClick}
        disabled={pending}
        title="Open a reflection on this thesis"
        className="text-text-secondary hover:text-text-primary"
      >
        {pending ? (
          <Loader2 className="animate-spin" aria-hidden />
        ) : (
          <NotebookPen aria-hidden />
        )}
        Reflect
      </Button>
    </span>
  )
}


function ClaimCard({ claim }: { claim: Claim }) {
  return (
    <Card className="[--card-spacing:--spacing(5)]">
      <div className="flex flex-col gap-4 px-(--card-spacing)">
        <div className="flex items-start justify-between gap-4">
          {/* Claim statement is prose — serif, ~16px, weight 400, comfortable leading. */}
          <p className="font-serif text-[16px] leading-[1.5] text-text-primary">
            {claim.statement}
          </p>
          <div className="flex shrink-0 items-center gap-2">
            <span className="rounded-4xl bg-surface-raised px-2 py-0.5 text-xs text-text-muted">
              {claim.is_core ? 'core' : 'minor'}
            </span>
            <StatusBadge status={claim.status} />
          </div>
        </div>

        <dl className="grid gap-3 sm:grid-cols-2">
          <Condition label="Proof condition" value={claim.proof_condition} />
          <Condition label="Break condition" value={claim.break_condition} />
        </dl>
      </div>
    </Card>
  )
}

function Condition({ label, value }: { label: string; value: string }) {
  return (
    <div>
      {/* Label stays small uppercase muted sans; the VALUE goes mono (a spec/rule),
          ~12.5px, a touch tighter than the serif statements. */}
      <dt className="text-xs tracking-wide text-text-muted uppercase">{label}</dt>
      <dd className="mt-1 font-mono text-[12.5px] leading-[1.4] text-text-secondary">
        {value}
      </dd>
    </div>
  )
}

function EvidenceCard({ event }: { event: EvidenceEvent }) {
  return (
    <Card className="[--card-spacing:--spacing(5)]">
      <div className="flex flex-col gap-3 px-(--card-spacing)">
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={event.verdict} />
          <span className="text-xs text-text-muted">
            {formatConfidence(event.confidence)} confidence
          </span>
          <span className="ml-auto text-xs text-text-muted">
            {formatDateTime(event.created_at)}
          </span>
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
      className="inline-flex items-center gap-1.5 rounded-lg text-sm text-text-secondary transition-colors hover:text-text-primary focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <ArrowLeft className="size-4" aria-hidden />
      All theses
    </Link>
  )
}

function DetailSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading thesis">
      <Skeleton className="h-4 w-24" />
      <div className="mt-6 mb-8 flex items-center gap-3">
        <Skeleton className="h-9 w-28" />
        <Skeleton className="h-5 w-24 rounded-4xl" />
      </div>
      <Skeleton className="mb-10 h-20 w-full" />
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
      <Card className="mt-6 [--card-spacing:--spacing(10)]">
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

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div>
      <BackLink />
      <Card className="mt-6 [--card-spacing:--spacing(6)]">
        <div className="flex flex-col items-start gap-4 px-(--card-spacing)">
          <div>
            <p className="text-sm font-medium text-text-primary">Couldn't load thesis</p>
            <p className="mt-1 text-sm text-status-broken">{message}</p>
          </div>
          <Button variant="outline" onClick={onRetry}>
            <RefreshCw aria-hidden />
            Retry
          </Button>
        </div>
      </Card>
    </div>
  )
}
