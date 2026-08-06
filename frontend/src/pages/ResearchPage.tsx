import { useCallback } from 'react'
import { ArrowLeft, ExternalLink, FileText, Info, RefreshCw } from 'lucide-react'
import { Link, useParams } from 'react-router'

import { CompanyLogo } from '@/components/CompanyLogo'
import { FilingsSection } from '@/components/filings/FilingsSection'
import { TickerNewsSection } from '@/components/news/TickerNewsSection'
import { ErrorState } from '@/components/ErrorState'
import { ResearchLoading } from '@/components/research/ResearchLoading'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useAsync } from '@/hooks/useAsync'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import {
  ApiError,
  getResearch,
  listHoldings,
  listTheses,
  type CompanyProfile,
  type Holding,
  type Research,
  type Thesis,
} from '@/lib/api'
import {
  formatCompactMoney,
  formatPlainDate,
  formatMoney,
  formatShares,
  formatSignedMoney,
  formatSignedPercent,
  signOf,
} from '@/lib/format'
import { cn } from '@/lib/utils'

interface ResearchData {
  research: Research
  thesis: Thesis | null
  holding: Holding | null
}

export function ResearchPage() {
  const { ticker = '' } = useParams<{ ticker: string }>()
  const symbol = ticker.toUpperCase()
  // The symbol comes from the URL, so it is known before the fetch resolves.
  useDocumentTitle(symbol || null)

  const load = useCallback(async (): Promise<ResearchData> => {
    // The research IS the page, so its failure is the page's failure.
    const research = await getResearch(symbol)

    // The user's own work is an overlay: a failure costs the badges, not the page.
    const [theses, portfolio] = await Promise.all([
      listTheses().catch(() => [] as Thesis[]),
      listHoldings().catch(() => null),
    ])

    const matching = theses
      .filter((item) => item.ticker === symbol)
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))

    return {
      research,
      thesis: matching[0] ?? null,
      holding: portfolio?.holdings.find((row) => row.ticker === symbol) ?? null,
    }
  }, [symbol])

  const { data, error, loading, reload } = useAsync<ResearchData>(load)

  if (loading) {
    return (
      <div>
        <BackLink />
        <h1 className="mt-6 mb-6 font-display text-3xl tracking-[0.01em] text-text-primary">
          {symbol}
        </h1>
        <ResearchLoading ticker={symbol} />
      </div>
    )
  }

  if (error || !data) {
    // A mistyped ticker is the common failure here, and it deserves better copy
    // than the generic 404 ("it may have been deleted") — so this one case keeps
    // its own wording. Everything else goes through the shared error copy.
    const notFound = error instanceof ApiError && error.status === 404
    return (
      <div>
        <BackLink />
        {notFound ? (
          <Card className="mt-6">
            <div className="flex flex-col items-start gap-4 px-(--card-spacing)" role="alert">
              <div>
                <p className="text-sm font-medium text-text-primary">
                  No company found for {symbol}
                </p>
                <p className="mt-1 text-sm text-status-broken">
                  Check the ticker symbol. Research covers US-listed companies.
                </p>
              </div>
            </div>
          </Card>
        ) : (
          <ErrorState
            error={error}
            subject="this company's research"
            onRetry={reload}
            className="mt-6"
          />
        )}
      </div>
    )
  }

  const { research, thesis, holding } = data

  return (
    <div>
      <BackLink />
      <ResearchHeader
        research={research}
        thesis={thesis}
        holding={holding}
        onRefresh={reload}
      />

      {/* Descriptions only. There is no card here that could hold a verdict. */}
      <div className="flex flex-col gap-4">
        {research.summary?.what_the_company_does && (
          <ProseCard title="What they do" body={research.summary.what_the_company_does} />
        )}
        {research.summary?.how_it_makes_money && (
          <ProseCard
            title="How they make money"
            body={research.summary.how_it_makes_money}
          />
        )}
        {research.summary && research.summary.key_risks.length > 0 && (
          <RisksCard risks={research.summary.key_risks} />
        )}

        {/* Falls back to the provider's own description when the filing summary is
            missing, so the page is never bare. Labelled differently because it is a
            different source, and pretending otherwise would undercut the footer. */}
        {!research.summary && research.profile?.long_business_summary && (
          <ProseCard
            title="Company description"
            body={research.profile.long_business_summary}
            source="From the company profile, not a filing."
          />
        )}

        {research.filing_summary_unavailable && (
          <FilingUnavailableNote reason={research.filing_summary_error} />
        )}

        {research.profile && <ProfileFacts profile={research.profile} />}
      </div>

      {research.source_filing_title && <SourceFooter research={research} />}

      {/* Below the footer, which closes off the one filing the page summarised
          automatically. This is the rest of them, each readable on request — and
          the same component the thesis page renders, so the two can never drift
          into describing filings differently.

          Claim links are ON here: the reader is on a company page, so a claim it
          names lives on a thesis page they would have to navigate to. */}
      <FilingsSection ticker={research.ticker} limit={8} className="mt-12" />

      {/* Below the filing summary AND below the footer naming its source, on
          purpose. Everything above restates one cited document; this is unverified
          links from elsewhere. Placing news between the summary and its attribution
          would break that pairing and blur exactly the line the footer draws. */}
      <TickerNewsSection ticker={research.ticker} limit={8} className="mt-12" />
    </div>
  )
}

function BackLink() {
  return (
    // See the matching back-link on ThesisDetailPage — the three are one set.
    <Link
      to="/market"
      className="nav-pill nav-pill-back w-fit focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <ArrowLeft className="nav-pill-arrow size-3" aria-hidden />
      Market
    </Link>
  )
}

function ResearchHeader({
  research,
  thesis,
  holding,
  onRefresh,
}: {
  research: Research
  thesis: Thesis | null
  holding: Holding | null
  onRefresh: () => void
}) {
  const profile = research.profile
  const tone = signOf(profile?.change ?? null)

  return (
    <header className="mt-6 mb-8 flex flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-0 items-start gap-3">
        <CompanyLogo ticker={research.ticker} logoUrl={research.logo_url} size={40} />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <h1 className="font-display text-3xl tracking-[0.01em] text-text-primary">
              {research.ticker}
            </h1>
            {profile?.name && (
              <span className="text-sm text-text-secondary">{profile.name}</span>
            )}
          </div>

          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
            {/* Absent for funds and trusts — the row disappears rather than
                showing an empty label. */}
            {profile?.sector && <span className="text-text-muted">{profile.sector}</span>}
            {profile?.price != null && (
              <span className="flex items-baseline gap-1.5">
                <span className="font-mono tabular-nums text-text-primary">
                  {formatMoney(profile.price)}
                </span>
                {profile.change != null && (
                  <span
                    className={cn(
                      'font-mono tabular-nums',
                      tone === 'positive'
                        ? 'text-status-strengthening'
                        : tone === 'negative'
                          ? 'text-status-broken'
                          : 'text-text-secondary',
                    )}
                  >
                    {formatSignedMoney(profile.change)} (
                    {formatSignedPercent(profile.change_percent)})
                  </span>
                )}
              </span>
            )}
          </div>

          {/* The user's own work, linking back across. */}
          {(thesis || holding) && (
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              {thesis && (
                <Link
                  to={`/theses/${thesis.id}`}
                  className="inline-flex rounded-xs focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  <StatusBadge status={thesis.status} />
                </Link>
              )}
              {/* ⚠️ A SURFACE, NOT A PILL. This is a VALUE, not an action — it
                  reports what you hold and happens to be clickable, so it must not
                  wear the outlined pill the back-links and "Company research" use.
                  It sits inline beside a StatusBadge, and that badge's opaque-ish
                  weight was exactly why a bare run of text next to it read as
                  underweight.

                  So it borrows the badge's GEOMETRY — same h-5, same rounded-xs,
                  same px-2, same mono 2xs — and takes a fill instead of an
                  outline: an outline here would have made it a second badge, and
                  a status badge that reports no status is the one thing this
                  cannot look like.

                  bg-surface-raised is #1d212b, a solid hex. That matters and is
                  not interchangeable with a translucent fill: the glow is BEHIND
                  this element, so anything you can see through still lets it
                  through. See the closing note on DashboardBackground, which
                  names a real surface as the lever for exactly this. */}
              {holding && (
                <Link
                  to="/portfolio"
                  className="inline-flex h-5 items-center rounded-xs bg-surface-raised px-2 font-mono text-2xs tabular-nums text-text-secondary transition-colors hover:text-text-primary focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  Held {formatShares(holding.shares)}
                </Link>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {!thesis && (
          <Button asChild variant="outline" size="sm">
            <Link to={`/theses/new?ticker=${encodeURIComponent(research.ticker)}`}>
              Write a thesis
            </Link>
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={onRefresh}>
          <RefreshCw aria-hidden />
          Refresh
        </Button>
      </div>
    </header>
  )
}

/**
 * Summary prose, in the SERIF face — it is writing, not data, and reads as such.
 * The chrome around it stays on the sans.
 */
function ProseCard({
  title,
  body,
  source,
}: {
  title: string
  body: string
  source?: string
}) {
  return (
    <Card>
      <div className="flex flex-col gap-2.5 px-(--card-spacing)">
        <h2 className="font-mono text-2xs tracking-[0.08em] text-text-muted uppercase">
          {title}
        </h2>
        <p className="font-serif text-base leading-relaxed text-text-primary">{body}</p>
        {source && <p className="text-xs text-text-muted">{source}</p>}
      </div>
    </Card>
  )
}

function RisksCard({ risks }: { risks: string[] }) {
  return (
    <Card>
      <div className="flex flex-col gap-2.5 px-(--card-spacing)">
        <h2 className="font-mono text-2xs tracking-[0.08em] text-text-muted uppercase">
          Key risks
        </h2>
        {/* The COMPANY's own stated risks, restated — not an assessment of how
            likely or serious they are, and deliberately not ranked. */}
        <p className="text-xs text-text-secondary">
          Risks the filing itself names, in no particular order.
        </p>
        <ul className="mt-0.5 flex flex-col gap-2">
          {risks.map((risk, index) => (
            <li
              key={index}
              className="flex gap-2.5 font-serif text-base leading-relaxed text-text-primary"
            >
              <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-text-muted" />
              <span>{risk}</span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  )
}

/** Facts from the provider's profile. Each row appears only if it has a value —
 *  funds have no sector, industry, headcount or website at all. */
function ProfileFacts({ profile }: { profile: CompanyProfile }) {
  const rows: Array<[string, string]> = []
  if (profile.industry) rows.push(['Industry', profile.industry])
  if (profile.employees != null) {
    rows.push(['Employees', formatShares(profile.employees)])
  }
  if (profile.market_cap != null) {
    rows.push(['Market cap', formatCompactMoney(profile.market_cap)])
  }
  if (rows.length === 0 && !profile.website) return null

  return (
    <Card>
      <div className="flex flex-col gap-3 px-(--card-spacing)">
        <h2 className="font-mono text-2xs tracking-[0.08em] text-text-muted uppercase">
          Company facts
        </h2>
        <dl className="grid grid-cols-1 gap-x-8 gap-y-2.5 sm:grid-cols-3">
          {rows.map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs text-text-muted">{label}</dt>
              <dd className="mt-0.5 font-mono text-sm tabular-nums text-text-primary">
                {value}
              </dd>
            </div>
          ))}
        </dl>
        {profile.website && (
          <a
            href={profile.website}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex w-fit items-center gap-1.5 rounded-lg text-xs text-text-secondary underline-offset-4 transition-colors hover:text-text-primary hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            {profile.website.replace(/^https?:\/\//, '')}
            <ExternalLink className="size-3" aria-hidden />
          </a>
        )}
      </div>
    </Card>
  )
}

/** Quiet, not an error: the profile above is still real and still useful. */
function FilingUnavailableNote({ reason }: { reason: string | null }) {
  return (
    <div className="flex items-start gap-2 px-1 text-sm text-text-secondary">
      <Info className="mt-0.5 size-4 shrink-0 text-text-muted" aria-hidden />
      <span>
        No filing summary this time — the SEC filing couldn't be read.{' '}
        <span className="text-text-muted" title={reason ?? undefined}>
          The company details above are unaffected.
        </span>
      </span>
    </div>
  )
}

/**
 * Names the exact document the summary came from. This is the point of the page:
 * without it these are generic paragraphs about a company, and with it they are a
 * restatement of a specific disclosure the reader can go and check.
 */
function SourceFooter({ research }: { research: Research }) {
  // EDGAR builds its title as "{ticker} {form} {date}", so the ISO date is usually
  // already in the link text. Appending a formatted "filed …" as well reads as two
  // different dates at a glance. Shown only when the title does not already carry it.
  const dateIsRedundant =
    research.source_filing_date != null &&
    (research.source_filing_title ?? '').includes(research.source_filing_date)

  return (
    <footer className="mt-6 flex flex-wrap items-center gap-1.5 px-1 text-xs text-text-muted">
      <FileText className="size-3.5 shrink-0" aria-hidden />
      <span>Summarised from</span>
      {research.source_filing_url ? (
        <a
          href={research.source_filing_url}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex items-center gap-1 rounded-lg text-text-secondary underline-offset-4 hover:text-text-primary hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {research.source_filing_title}
          <ExternalLink className="size-3" aria-hidden />
        </a>
      ) : (
        <span className="text-text-secondary">{research.source_filing_title}</span>
      )}
      {research.source_filing_date && !dateIsRedundant && (
        <span>· filed {formatPlainDate(research.source_filing_date)}</span>
      )}
    </footer>
  )
}

