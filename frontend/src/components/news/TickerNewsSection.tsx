import { useId } from 'react'
import { Newspaper } from 'lucide-react'
import { Link } from 'react-router'

import { Count } from '@/components/Count'
import { INSET_SURFACE } from '@/components/StatusSurface'
import { NewsList } from '@/components/news/NewsList'
import { useTickerNews } from '@/hooks/useNews'
import { cn } from '@/lib/utils'

/**
 * Recent headlines for one ticker, as a page section.
 *
 * ⚠️ NEWS IS NOT EVIDENCE, and this section exists to keep the two from ever
 * reading as the same kind of thing. Evidence is a passage quoted from a named
 * filing, checked against a specific claim, and carrying a status the engine
 * derived. A headline is a link someone else published that nobody has verified.
 * So: its own section with its own heading, a standing note saying what it is, flat
 * rows rather than the cards evidence and claims use, and NO status badges — the
 * rows come from NewsItem, which has never had one.
 *
 * Owns no row markup of its own: NewsList renders every state (loading, error,
 * empty, loaded) exactly as it does in the slide-over panel and on /news.
 */
export function TickerNewsSection({
  ticker,
  limit,
  moreHref,
  moreLabel,
  className,
}: {
  ticker: string
  limit: number
  /** Optional "there is more of this elsewhere" link. Omitted when this section is
   *  already the fullest view of the ticker's news. */
  moreHref?: string
  moreLabel?: string
  className?: string
}) {
  const { items, loading, error, reload } = useTickerNews(ticker, limit)
  const headingId = useId()

  return (
    <section aria-labelledby={headingId} className={cn(className)}>
      <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2
          id={headingId}
          className="flex items-center gap-2 font-heading text-sm font-medium tracking-wide text-text-primary uppercase"
        >
          <Newspaper className="size-3.5 text-text-muted" aria-hidden />
          Recent news
          {/* Only once loaded — a count that appears, then changes, is worse than
              one that arrives with the list it describes. */}
          {!loading && !error && <Count value={items.length} />}
        </h2>
        {moreHref && (
          <Link
            to={moreHref}
            className="inline-flex items-center gap-1 rounded-lg text-sm text-text-secondary transition-colors hover:text-text-primary focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            {moreLabel}
            <span aria-hidden>→</span>
          </Link>
        )}
      </div>

      {/* Says what these are BEFORE the reader starts weighing them. Permanent, not
          an empty state or a warning — the distinction holds when the list is full. */}
      <p className="mb-3 text-xs text-text-secondary">
        Unverified headlines from around the web. Nothing here has been checked
        against a filing.
      </p>

      {/* The same opaque inset card the filings section sits in, for the same
          reason: these rows were on the raw page, where the ambient backdrop
          glowed through them. The heading and the standing note stay OUTSIDE it
          — they label the section, they are not part of the list.

          The card carries no padding of its own; the rows carry theirs, so the
          hairline between two headlines runs the full width of the card instead
          of stopping 16px short at each end. */}
      <div className={cn('overflow-hidden bg-surface-inset', INSET_SURFACE)}>
        <NewsList
          items={items}
          loading={loading}
          error={error}
          onRetry={reload}
          emptyMessage={`No recent news for ${ticker}.`}
          rowClassName="px-4"
        />
      </div>
    </section>
  )
}
