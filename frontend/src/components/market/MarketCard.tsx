import { Link } from 'react-router'

import { CompanyLogo } from '@/components/CompanyLogo'
import { Sparkline } from '@/components/Sparkline'
import { StatusBadge } from '@/components/StatusBadge'
import { Card } from '@/components/ui/card'
import { TruncatedText } from '@/components/ui/tooltip'
import type { Holding, Quote, Thesis } from '@/lib/api'
import {
  UNAVAILABLE,
  formatCompactMoney,
  formatMoney,
  formatShares,
  formatSignedMoney,
  formatSignedPercent,
  signOf,
} from '@/lib/format'
import { cn } from '@/lib/utils'

/**
 * One company.
 *
 * ⚠️ FACTS ONLY. Size, price, today's move, and whether you have written or bought
 * anything here. No card is ever labelled a leader, a mover or an opportunity, and
 * nothing on it is ordered or coloured to imply that one company is a better idea
 * than another — the green and red are the arithmetic sign of today's change and
 * nothing more.
 */
export function MarketCard({
  quote,
  thesis,
  holding,
}: {
  quote: Quote
  /** The user's thesis for this ticker, if they wrote one. */
  thesis: Thesis | null
  /** Their position in it, if they hold it. */
  holding: Holding | null
}) {
  const tone = signOf(quote.change)

  return (
    <Card>
      {/* A container, so the sparkline below can be dropped by how much room
          THIS CARD has rather than by viewport width. The two are not the same
          here: the grid's `sm:` breakpoint reads the viewport, but the sidebar
          takes 240px out of it first, so a 640px window renders two columns into
          a 400px strip and each card ends up ~148px wide. */}
      <div className="@container flex h-full flex-col gap-3 px-(--card-spacing)">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <CompanyLogo ticker={quote.ticker} logoUrl={quote.logo_url} size={32} />
            <div className="min-w-0">
              {/* The ticker is the way in to research — the same affordance on
                  every surface where a ticker appears. */}
              <Link
                to={`/research/${encodeURIComponent(quote.ticker)}`}
                className="rounded-lg font-mono text-sm text-text-primary underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                {quote.ticker}
              </Link>
              {/* Null while unavailable — the ticker above still names the card. */}
              {quote.company_name ? (
                // The card is a grid cell, so a long name ("Taiwan Semiconductor
                // Manufacturing Company Limited") is always clipped. TruncatedText
                // only offers the tooltip when it measures as actually clipped.
                <TruncatedText
                  text={quote.company_name}
                  className="text-xs text-text-secondary"
                />
              ) : (
                <div className="truncate text-xs text-text-secondary">{UNAVAILABLE}</div>
              )}
            </div>
          </div>
          <MarketCap value={quote.market_cap} />
        </div>

        {quote.unavailable ? (
          <Unavailable reason={quote.error} />
        ) : (
          <div className="flex items-end justify-between gap-3">
            <div className="flex min-w-0 flex-wrap items-baseline gap-x-2.5">
              <span className="font-mono text-xl tabular-nums text-text-primary">
                {formatMoney(quote.price)}
              </span>
              <span
                className={cn(
                  'font-mono text-xs tabular-nums',
                  tone === 'positive'
                    ? 'text-status-strengthening'
                    : tone === 'negative'
                      ? 'text-status-broken'
                      : 'text-text-secondary',
                )}
              >
                {/* Both carry their own sign, so colour is never the only signal. */}
                {formatSignedMoney(quote.change)} ({formatSignedPercent(quote.change_percent)})
              </span>
            </div>
            {/* Beside today's move, which it puts in context: the coloured figure
                is one session, the line behind it is thirty. The line itself is
                NEVER coloured by direction — see Sparkline.

                ⚠️ DROPPED ENTIRELY ON A NARROW CARD rather than squeezed. At 72px
                it was taking half of a 148px card and crushing the price beside it
                to 24px of overflowing text. The price is the card's reason for
                existing and the sparkline is context for it, so when only one fits,
                it is not the sparkline. */}
            <Sparkline
              ticker={quote.ticker}
              days={30}
              width={72}
              height={24}
              className="hidden @[240px]:inline-block"
            />
          </div>
        )}

        {/* ⭐ What makes this the user's page rather than a stock ticker: their own
            work, shown against the company. Pushed to the bottom so every card's
            connection line sits on the same baseline across the grid. */}
        {/* `min-h-6` (24px) is the StatusBadge's 20px plus this row's own 4px
            `pt-1`, because min-height is border-box — min-h-5 was satisfied by a
            16px "Track this" link plus that same padding and left the badge row
            4px taller. It makes a card carrying a badge and one carrying the plain
            link the same height: without it the grid had two row heights AND every
            card grew the moment the theses request landed after the quotes. */}
        <div className="mt-auto flex min-h-6 flex-wrap items-center gap-2 pt-1">
          <Connection ticker={quote.ticker} thesis={thesis} holding={holding} />
        </div>
      </div>
    </Card>
  )
}

function MarketCap({ value }: { value: number | null }) {
  return (
    <div className="shrink-0 text-right">
      <div className="font-mono text-2xs tracking-[0.08em] text-text-muted uppercase">
        Mkt cap
      </div>
      <div className="font-mono text-sm tabular-nums text-text-secondary">
        {value === null ? (
          <span className="text-text-muted">
            <span aria-hidden>{UNAVAILABLE}</span>
            <span className="sr-only">unavailable</span>
          </span>
        ) : (
          formatCompactMoney(value)
        )}
      </div>
    </div>
  )
}

/**
 * Shown in place of the price when the quote failed. Never a 0, and never a bare
 * dash on its own here — with no number beside it the card has room to say what
 * actually happened.
 */
function Unavailable({ reason }: { reason: string | null }) {
  return (
    <div>
      <p className="font-mono text-xl text-text-muted">
        <span aria-hidden>{UNAVAILABLE}</span>
        <span className="sr-only">Price unavailable</span>
      </p>
      <p className="text-xs text-text-secondary" title={reason ?? undefined}>
        Quote unavailable
      </p>
    </div>
  )
}

/**
 * The thesis and the position, or an invitation to start one.
 *
 * "Track this" is deliberately quiet — muted text, no button, no count badge.
 * Not having a thesis on one of the twelve largest companies is a normal state, not
 * an omission to be chased about.
 */
function Connection({
  ticker,
  thesis,
  holding,
}: {
  ticker: string
  thesis: Thesis | null
  holding: Holding | null
}) {
  if (!thesis && !holding) {
    return (
      <Link
        to={`/theses/new?ticker=${encodeURIComponent(ticker)}`}
        className="rounded-lg text-xs text-text-muted underline-offset-4 transition-colors hover:text-text-secondary hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        Track this
      </Link>
    )
  }

  return (
    <>
      {thesis && (
        <Link
          to={`/theses/${thesis.id}`}
          className="inline-flex rounded-xs focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <StatusBadge status={thesis.status} />
        </Link>
      )}
      {holding && (
        <Link
          to="/portfolio"
          className="rounded-lg font-mono text-xs tabular-nums text-text-secondary underline-offset-4 transition-colors hover:text-text-primary hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {/* Size only. What it is worth lives on the portfolio page; repeating the
              P&L here would put a gain or loss next to a price with no context. */}
          Held {formatShares(holding.shares)}
        </Link>
      )}
      {/* Owned but never written up — the invitation still applies. */}
      {!thesis && holding && (
        <Link
          to={`/theses/new?ticker=${encodeURIComponent(ticker)}`}
          className="rounded-lg text-xs text-text-muted underline-offset-4 transition-colors hover:text-text-secondary hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          Track this
        </Link>
      )}
    </>
  )
}
