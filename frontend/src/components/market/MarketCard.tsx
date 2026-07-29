import { Link } from 'react-router'

import { CompanyLogo } from '@/components/CompanyLogo'
import { StatusBadge } from '@/components/StatusBadge'
import { Card } from '@/components/ui/card'
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
    <Card className="[--card-spacing:--spacing(5)]">
      <div className="flex h-full flex-col gap-3 px-(--card-spacing)">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <CompanyLogo ticker={quote.ticker} logoUrl={quote.logo_url} size={32} />
            <div className="min-w-0">
              {/* The ticker is the way in to research — the same affordance on
                  every surface where a ticker appears. */}
              <Link
                to={`/research/${encodeURIComponent(quote.ticker)}`}
                className="rounded font-mono text-sm text-text-primary underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                {quote.ticker}
              </Link>
              <div className="truncate text-xs text-text-secondary">
                {/* Null while unavailable — the ticker above still names the card. */}
                {quote.company_name ?? UNAVAILABLE}
              </div>
            </div>
          </div>
          <MarketCap value={quote.market_cap} />
        </div>

        {quote.unavailable ? (
          <Unavailable reason={quote.error} />
        ) : (
          <div className="flex items-baseline gap-2.5">
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
        )}

        {/* ⭐ What makes this the user's page rather than a stock ticker: their own
            work, shown against the company. Pushed to the bottom so every card's
            connection line sits on the same baseline across the grid. */}
        <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
          <Connection ticker={quote.ticker} thesis={thesis} holding={holding} />
        </div>
      </div>
    </Card>
  )
}

function MarketCap({ value }: { value: number | null }) {
  return (
    <div className="shrink-0 text-right">
      <div className="font-mono text-[10px] tracking-[0.08em] text-text-muted uppercase">
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
          className="inline-flex rounded-[4px] focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <StatusBadge status={thesis.status} />
        </Link>
      )}
      {holding && (
        <Link
          to="/portfolio"
          className="rounded-lg font-mono text-xs text-text-secondary underline-offset-4 transition-colors hover:text-text-primary hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
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
