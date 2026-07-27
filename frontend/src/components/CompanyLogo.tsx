import { useState } from 'react'

import { cn } from '@/lib/utils'

/**
 * The company mark shown beside a ticker. ONE component for every place a ticker
 * appears — the thesis list, the thesis detail header, news rows and reflection cards.
 *
 * Purely decorative: the ticker itself is always rendered next to it as text, so this
 * is aria-hidden with an empty alt rather than announcing the company twice.
 *
 * The box is ALWAYS rendered at its full size, whether the image loads, fails, or was
 * never available — so rows never reflow as logos arrive.
 */
export function CompanyLogo({
  ticker,
  logoUrl,
  size = 32,
  className,
}: {
  ticker: string
  /**
   * Derived by the backend from a curated ticker->domain map. Null for anything not
   * in it — the initials fallback is the normal case for smaller companies, not an
   * error state.
   */
  logoUrl?: string | null
  size?: number
  className?: string
}) {
  const [failed, setFailed] = useState(false)
  const showImage = Boolean(logoUrl) && !failed

  return (
    <span
      aria-hidden
      style={{ width: size, height: size }}
      className={cn(
        // The border matters: many company marks are white or near-white and would
        // otherwise float shapelessly on the dark background.
        'inline-flex shrink-0 items-center justify-center overflow-hidden rounded-lg border border-border bg-surface-raised',
        className,
      )}
    >
      {showImage ? (
        <img
          src={logoUrl!}
          alt=""
          loading="lazy"
          // Falls back to initials rather than leaving a broken-image glyph.
          onError={() => setFailed(true)}
          // Don't leak which theses are being viewed to the icon host.
          referrerPolicy="no-referrer"
          className="size-full object-contain"
        />
      ) : (
        <InitialsFallback ticker={ticker} size={size} />
      )}
    </span>
  )
}

/**
 * The fallback has to look deliberate rather than broken, because for most tickers it
 * IS the design — the curated domain map covers large caps only.
 */
function InitialsFallback({ ticker, size }: { ticker: string; size: number }) {
  // Two letters read as a monogram; one looks like a typo. Punctuation is dropped so
  // "BRK.B" becomes "BR" rather than "B.".
  const initials = ticker.replace(/[^A-Za-z]/g, '').slice(0, 2).toUpperCase() || '—'

  return (
    <span
      // Scaled to the box so one component serves a 20px news row and a 40px header.
      style={{ fontSize: Math.max(9, Math.round(size * 0.38)) }}
      className="font-mono leading-none tracking-tight text-text-secondary"
    >
      {initials}
    </span>
  )
}
