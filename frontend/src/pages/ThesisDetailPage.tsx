import { useCallback, type ReactNode } from 'react'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import { Link, useParams } from 'react-router'

import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAsync } from '@/hooks/useAsync'
import {
  ApiError,
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

  const { data, error, loading, reload } = useAsync<DetailData>(load)

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

      <header className="mt-6 mb-8 flex flex-wrap items-center gap-3">
        <h1 className="font-heading text-3xl font-medium text-text-primary">
          {thesis.ticker}
        </h1>
        <StatusBadge status={thesis.status} />
        <span className="ml-auto text-sm text-text-muted">
          Created {formatDate(thesis.created_at)}
        </span>
      </header>

      <section className="mb-10">
        <SectionHeading>Original reasoning</SectionHeading>
        <blockquote className="border-l-2 border-border pl-4 text-sm leading-relaxed whitespace-pre-wrap text-text-secondary">
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

function ClaimCard({ claim }: { claim: Claim }) {
  return (
    <Card className="[--card-spacing:--spacing(5)]">
      <div className="flex flex-col gap-4 px-(--card-spacing)">
        <div className="flex items-start justify-between gap-4">
          <p className="text-sm leading-relaxed text-text-primary">{claim.statement}</p>
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
      <dt className="text-xs tracking-wide text-text-muted uppercase">{label}</dt>
      <dd className="mt-1 text-sm leading-relaxed text-text-secondary">{value}</dd>
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
