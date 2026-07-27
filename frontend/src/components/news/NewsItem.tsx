import { useState } from 'react'
import { ExternalLink } from 'lucide-react'

import { CompanyLogo } from '@/components/CompanyLogo'
import { formatRelative } from '@/lib/format'
import type { NewsItem as NewsItemData } from '@/lib/api'

/**
 * Publisher favicon, purely decorative — the source name sits right beside it, so
 * alt="" and aria-hidden keep a screen reader from announcing the publisher twice.
 *
 * The 16px box is ALWAYS rendered, even with no icon to show, so rows keep their
 * height and the list never reflows as images arrive or fail.
 */
function SourceIcon({ src }: { src: string | null }) {
  const [failed, setFailed] = useState(false)

  return (
    <span className="inline-flex size-4 shrink-0 items-center justify-center">
      {src && !failed && (
        <img
          src={src}
          alt=""
          aria-hidden
          loading="lazy"
          // Leaves empty (but reserved) space rather than a broken-image glyph. This
          // fires when no image arrives at all — DNS failure, a blocked request, the
          // icon host being down. An unrecognised publisher does NOT land here: the
          // service answers with a neutral placeholder image, which simply renders.
          onError={() => setFailed(true)}
          // Don't leak which page the reader is on to the icon host.
          referrerPolicy="no-referrer"
          className="size-4 rounded-[3px] object-contain"
        />
      )}
    </span>
  )
}

/**
 * One headline row. Flat — no glass, no card chrome — because this renders inside
 * both the panel and the page and must stay the most legible surface in each.
 */
export function NewsItem({ item }: { item: NewsItemData }) {
  return (
    <article className="flex flex-col gap-1.5 border-b border-border py-3 last:border-b-0">
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group/headline flex items-start gap-1.5 rounded-lg text-sm leading-snug text-text-primary transition-colors hover:text-text-primary/80 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <span>{item.title}</span>
        <ExternalLink
          aria-hidden
          className="mt-0.5 size-3 shrink-0 text-text-muted opacity-0 transition-opacity group-hover/headline:opacity-100"
        />
        <span className="sr-only">(opens in a new tab)</span>
      </a>

      <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
        {/* Company logo + ticker. Distinct from the publisher icon further along the
            row: this is who the story is ABOUT, that is who reported it. */}
        <span className="flex items-center gap-1.5">
          <CompanyLogo ticker={item.ticker} logoUrl={item.logo_url} size={16} />
          <span className="rounded-[4px] border border-border px-1.5 py-0.5 font-mono tracking-[0.08em] text-text-secondary uppercase">
            {item.ticker}
          </span>
        </span>
        <span className="flex min-w-0 items-center gap-1.5">
          <SourceIcon src={item.favicon_url} />
          <span className="truncate">{item.source}</span>
        </span>
        <span aria-hidden>·</span>
        {/* published_at is deliberately nullable upstream — show the absence rather
            than a fabricated timestamp. */}
        <span>{item.published_at ? formatRelative(item.published_at) : 'no date'}</span>
      </div>
    </article>
  )
}
