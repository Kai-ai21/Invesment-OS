import { useCallback, useId, useState } from 'react'
import { ArrowRight, ExternalLink, FileText, Loader2 } from 'lucide-react'
import { Link } from 'react-router'

import { Count } from '@/components/Count'
import { ErrorState } from '@/components/ErrorState'
import { INSET_SURFACE } from '@/components/StatusSpine'
import { Skeleton } from '@/components/ui/skeleton'
import { useAsync } from '@/hooks/useAsync'
import {
  listFilings,
  summariseFiling,
  type Filing,
  type FilingSummary,
} from '@/lib/api'
import { describeError } from '@/lib/errors'
import { formatPlainDate } from '@/lib/format'
import { cn } from '@/lib/utils'

/**
 * A company's recent SEC filings, each of which can be read back in plain language
 * without leaving the page.
 *
 * ⚠️ A SUMMARY IS NOT EVIDENCE, and this section exists to keep the two from ever
 * reading as the same thing — the same job TickerNewsSection does for headlines,
 * and for a sharper reason: a filing summary is drawn from a real SEC document, so
 * it is far more plausibly mistaken for the evidence log than a news link is.
 *
 * Evidence is a passage quoted verbatim from a named filing, judged against one
 * specific claim, carrying a confidence score and a verdict the status engine acts
 * on. A summary is an AI reading of retrieved passages that nobody has checked, and
 * producing one writes nothing at all. So this section keeps:
 *   - its own heading and a standing note saying what these are
 *   - flat rows rather than the Cards claims and evidence use
 *   - NO StatusBadge anywhere; the form chip is neutral and carries no status colour
 *   - no verdict, confidence or direction language, because the API has no such
 *     field to render (see FilingSummary in lib/api.ts)
 * The one place it touches the user's own work is `relevance`, which says a filing
 * DISCUSSES a claim and never which way it points.
 *
 * ONE component, rendered by both the thesis detail page and /research/{ticker}.
 * They differ only in whether a claim link can go anywhere, which `linkClaims`
 * decides.
 */
export function FilingsSection({
  ticker,
  limit = 8,
  linkClaims = true,
  className,
}: {
  ticker: string
  limit?: number
  /** Whether `relevance` renders claim links. Off where the claims are already on
   *  screen — a link to the page you are on is furniture, not navigation. */
  linkClaims?: boolean
  className?: string
}) {
  const headingId = useId()
  const load = useCallback(() => listFilings(ticker, limit), [ticker, limit])
  const { data, error, loading, reload } = useAsync<Filing[]>(load)
  const filings = data ?? []

  // Which row is expanded, and every summary fetched so far.
  //
  // ⚠️ THE CACHE IS WHY THIS STATE LIVES HERE rather than in each row. A summary
  // costs 10-20 seconds and an AI call, so collapsing a row and opening it again
  // must not pay for it twice. Keyed by accession number — the SEC's own id, the
  // same key the backend's 30-day cache uses.
  const [openAccession, setOpenAccession] = useState<string | null>(null)
  const [summaries, setSummaries] = useState<Record<string, FilingSummary>>({})
  const [pending, setPending] = useState<string | null>(null)
  const [failures, setFailures] = useState<Record<string, string>>({})

  const toggle = useCallback(
    async (filing: Filing) => {
      const key = filing.accession_number
      if (openAccession === key) {
        setOpenAccession(null)
        return
      }
      setOpenAccession(key)

      // Already read, or being read right now — either way, do not ask again.
      if (summaries[key] || pending === key) return

      setPending(key)
      setFailures((current) => {
        if (!(key in current)) return current
        const { [key]: _removed, ...rest } = current
        return rest
      })
      try {
        const summary = await summariseFiling(ticker, filing)
        setSummaries((current) => ({ ...current, [key]: summary }))
      } catch (cause: unknown) {
        // Inline and per row: one filing that could not be read must not take the
        // list down with it, and the other rows are still summarisable.
        setFailures((current) => ({
          ...current,
          [key]: describeError(cause, 'this filing').detail,
        }))
      } finally {
        setPending((current) => (current === key ? null : current))
      }
    },
    [openAccession, pending, summaries, ticker],
  )

  return (
    <section aria-labelledby={headingId} className={cn(className)}>
      <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2
          id={headingId}
          className="flex items-center gap-2 font-heading text-sm font-medium tracking-wide text-text-primary uppercase"
        >
          <FileText className="size-3.5 text-text-muted" aria-hidden />
          Filings
          {/* Only once loaded — a count that appears and then changes is worse
              than one that arrives with the list it describes. */}
          {!loading && !error && <Count value={filings.length} />}
        </h2>
      </div>

      {/* Says what these are BEFORE the reader starts weighing them. Permanent,
          not an empty state and not a warning — the distinction holds when the
          list is full and every row has been read. */}
      <p className="mb-3 text-xs text-text-secondary">
        The company's own SEC filings, summarised on request. Reading only — nothing
        here is checked against your claims or recorded as evidence.
      </p>

      {/* ⚠️ THE ROWS NEEDED A SURFACE, AND IT HAS TO BE OPAQUE. They used to sit
          on the page itself, which on this page is not a flat colour — the
          ambient backdrop glows through it, and it was landing straight behind
          the "Summarise" pills and washing out their edges.

          `bg-surface-inset` is a solid #0a0c10, so the glow stops at the card. A
          translucent fill would NOT have fixed this: the glow is behind the
          section, so anything you can see through still lets it through, which
          is the whole reason the section reads as flat now and did not before.

          Same inset shell as the thesis cards — see INSET_SURFACE. `flat` — no
          hover — because the card is a container, not a target; the ROWS inside
          it are the things you can point at.

          `overflow-hidden` so a row's hover fill is cut to the card's corners
          instead of squaring off the top and bottom of the list. */}
      <div className={cn('overflow-hidden bg-surface-inset', INSET_SURFACE)}>
        {loading ? (
          <FilingsSkeleton />
        ) : error ? (
          <div className="px-4 py-3">
            <ErrorState
              error={error}
              subject="this company's filings"
              onRetry={reload}
              bare
            />
          </div>
        ) : filings.length === 0 ? (
          <p className="px-4 py-3 text-sm text-text-secondary">
            No recent 10-K, 10-Q or 8-K filings for {ticker}.
          </p>
        ) : (
          <ul className="flex flex-col">
            {filings.map((filing) => {
              const key = filing.accession_number
              return (
                <li key={key} className="border-b border-border last:border-b-0">
                  <FilingRow
                    filing={filing}
                    open={openAccession === key}
                    loading={pending === key}
                    summary={summaries[key] ?? null}
                    failure={failures[key] ?? null}
                    linkClaims={linkClaims}
                    onToggle={() => void toggle(filing)}
                  />
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </section>
  )
}

function FilingRow({
  filing,
  open,
  loading,
  summary,
  failure,
  linkClaims,
  onToggle,
}: {
  filing: Filing
  open: boolean
  loading: boolean
  summary: FilingSummary | null
  failure: string | null
  linkClaims: boolean
  onToggle: () => void
}) {
  const panelId = `filing-${filing.accession_number}`

  return (
    <div>
      {/* ⚠️ THE HOVER FILL IS ON THIS LINE, NOT ON THE WHOLE ROW COMPONENT, and
          the padding is here rather than on the card for the same reason: the
          highlight has to run edge to edge, and the expanded summary below must
          NOT light up with it. Tinting a 400px panel of prose because the cursor
          crossed it is not feedback, it is the page flinching.

          3% white — enough to say "this line is one unit and it is pointable",
          quiet enough that scrolling past a list of eight does not strobe. The
          pill inside keeps its own, brighter hover; see .filing-action. */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 transition-colors hover:bg-white/[0.03]">
        {/* ⚠️ NEUTRAL BY DESIGN. This is the position a StatusBadge occupies on an
            evidence or claim card, so it deliberately does not look like one: no
            status colour, a border rather than a fill, and the same chip the news
            rows use for a ticker. A filing has no status to report. */}
        <span className="shrink-0 rounded-xs border border-border px-1.5 py-0.5 font-mono text-2xs tracking-[0.08em] text-text-secondary uppercase">
          {filing.form}
        </span>

        <span className="font-mono text-xs tabular-nums text-text-muted">
          {formatPlainDate(filing.filing_date)}
        </span>

        <a
          href={filing.url}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex min-w-0 items-center gap-1 rounded-lg text-sm text-text-secondary underline-offset-4 transition-colors hover:text-text-primary hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <span className="truncate">{filing.title}</span>
          <ExternalLink className="size-3 shrink-0" aria-hidden />
        </a>

        {/* ⚠️ NOT the shared <Button>, and emphatically not the gradient variant —
            see .filing-action in index.css for why a repeated row action gets its
            own quiet pill. `data-expanded` drives the arrow's rotation there;
            aria-expanded is what a screen reader reads, and CSS cannot depend on
            it alone without the two silently drifting apart. */}
        <button
          type="button"
          onClick={onToggle}
          disabled={loading}
          data-expanded={open}
          aria-expanded={open}
          aria-controls={panelId}
          className="filing-action ml-auto shrink-0 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {loading ? (
            <Loader2 className="size-3 animate-spin" aria-hidden />
          ) : (
            // LEFT of the label, deliberately: it reads as "open this", pointing
            // into the row rather than off the end of it.
            <ArrowRight className="filing-action-arrow size-3" aria-hidden />
          )}
          {/* Three labels for three states. "Summarise" is a request for work;
              "Hide" is the collapse of something already read — the second press
              costs nothing, and the word should not imply it does. */}
          {loading ? 'Reading…' : open ? 'Hide' : 'Summarise'}
        </button>
      </div>

      {open && (
        <div id={panelId} className="mx-4 mb-3 border-l-2 border-border pl-4">
          {loading ? (
            <ReadingNote />
          ) : failure ? (
            <p className="text-sm text-status-broken" role="alert">
              {failure}
            </p>
          ) : summary ? (
            <SummaryBody summary={summary} linkClaims={linkClaims} />
          ) : null}
        </div>
      )}
    </div>
  )
}

/** 10-20 seconds is normal, so this says what is happening rather than spinning
 *  silently — a bare spinner at that length reads as a hang. */
function ReadingNote() {
  return (
    <p className="flex items-center gap-2 text-sm text-text-secondary" role="status">
      <Loader2 className="size-3.5 animate-spin" aria-hidden />
      Reading the filing…
      <span className="text-text-muted">this takes 10-20 seconds</span>
    </p>
  )
}

/**
 * "an 8-K", but "a 10-K" and "a 10-Q" — the article follows how the form is SAID,
 * not how it is spelt, and "8" is the only one of these that starts on a vowel
 * sound ("eight-kay"). A bare `a ${form}` printed "What a 8-K is" on every 8-K,
 * which is most of the list.
 *
 * Keyed on the leading digit rather than a list of forms, so an amendment (8-K/A)
 * or a form we have not seen still reads correctly.
 */
function articleFor(form: string): string {
  return /^8/.test(form.trim()) ? 'an' : 'a'
}

function SummaryBody({
  summary,
  linkClaims,
}: {
  summary: FilingSummary
  linkClaims: boolean
}) {
  return (
    <div className="flex flex-col gap-5">
      {/* What this KIND of document is for — the context that makes the rest
          readable to someone who has never opened a filing. */}
      <SummaryBlock title={`What ${articleFor(summary.filing.form)} ${summary.filing.form} is`}>
        <p className="font-serif text-base leading-relaxed text-text-primary">
          {summary.filing_type_explained}
        </p>
      </SummaryBlock>

      {summary.key_points.length > 0 && (
        <SummaryBlock title="What this one says">
          <ul className="flex flex-col gap-2">
            {summary.key_points.map((point, index) => (
              <li
                key={index}
                className="flex gap-2.5 font-serif text-base leading-relaxed text-text-primary"
              >
                <span
                  aria-hidden
                  className="mt-2 size-1 shrink-0 rounded-full bg-text-muted"
                />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </SummaryBlock>
      )}

      {summary.notable_numbers.length > 0 && (
        <SummaryBlock title="Numbers it reports">
          {/* Mono and tabular for the figures, sans for what they measure. A
              figure without its subject is a number the reader has to re-derive
              the meaning of, so the two are always rendered as a pair. */}
          <dl className="flex flex-col gap-2.5">
            {summary.notable_numbers.map((entry, index) => (
              <div key={index} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                <dt className="font-mono text-sm tabular-nums text-text-primary">
                  {entry.figure}
                </dt>
                <dd className="text-sm text-text-secondary">{entry.what_it_measures}</dd>
              </div>
            ))}
          </dl>
        </SummaryBlock>
      )}

      <RelevanceBlock summary={summary} linkClaims={linkClaims} />
    </div>
  )
}

/**
 * Which of the user's own claims this filing talks about.
 *
 * ⚠️ THE WORDING IS THE WHOLE POINT. "Touches" and "discusses", never "supports",
 * "confirms" or "contradicts" — the summary was never checked against the claim,
 * and this is the block most at risk of being read as a verdict because it is the
 * one that names the user's own work. The empty case says so plainly rather than
 * apologising: no overlap is the normal, expected outcome.
 */
function RelevanceBlock({
  summary,
  linkClaims,
}: {
  summary: FilingSummary
  linkClaims: boolean
}) {
  if (summary.relevance.length === 0) {
    return (
      <SummaryBlock title="Your claims">
        <p className="text-sm text-text-secondary">
          Doesn't directly address your claims.
        </p>
      </SummaryBlock>
    )
  }

  return (
    <SummaryBlock title="Your claims">
      <p className="mb-2 text-xs text-text-secondary">
        Claims this filing talks about. Whether it supports them is a separate
        question — run a check for that.
      </p>
      <ul className="flex flex-col gap-2">
        {summary.relevance.map((claim) => (
          <li key={claim.claim_id} className="flex gap-2.5">
            <span
              aria-hidden
              className="mt-2 size-1 shrink-0 rounded-full bg-text-muted"
            />
            {linkClaims ? (
              <Link
                to={`/theses/${encodeURIComponent(claim.thesis_id)}`}
                className="rounded-lg font-serif text-base leading-relaxed text-text-primary underline-offset-4 transition-colors hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                {claim.statement}
              </Link>
            ) : (
              <span className="font-serif text-base leading-relaxed text-text-primary">
                {claim.statement}
              </span>
            )}
          </li>
        ))}
      </ul>
    </SummaryBlock>
  )
}

/** Section heading inside an expanded row. Mono/uppercase/muted, matching the
 *  research page's card headings — small enough to separate the four blocks
 *  without competing with the page's own section headings. */
function SummaryBlock({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div>
      <h3 className="mb-2 font-mono text-2xs tracking-[0.08em] text-text-muted uppercase">
        {title}
      </h3>
      {children}
    </div>
  )
}

function FilingsSkeleton() {
  return (
    <div className="flex flex-col" aria-busy="true" aria-label="Loading filings">
      {[0, 1, 2, 3].map((row) => (
        <div
          key={row}
          // px-4 matches the loaded row's padding — without it the list shifts
          // sideways by 16px at the moment the filings arrive.
          className="flex items-center gap-3 border-b border-border px-4 py-3 last:border-b-0"
        >
          <Skeleton className="h-5 w-12 rounded-xs" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="ml-auto h-4 w-20" />
        </div>
      ))}
    </div>
  )
}
