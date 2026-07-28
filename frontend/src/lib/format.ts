/**
 * The backend builds timestamps with `datetime.now(timezone.utc)` but stores them
 * in a naive column, so FastAPI serialises them with no timezone designator.
 * `new Date()` reads such a string as LOCAL time, which shifts every date by the
 * viewer's UTC offset — very visible on relative dates. Re-attach the UTC marker
 * unless the string already carries a zone.
 */
function parseBackendDate(iso: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso)
  return new Date(hasZone ? iso : `${iso}Z`)
}

export function formatDate(iso: string): string {
  const date = parseBackendDate(iso)
  if (Number.isNaN(date.getTime())) return 'unknown date'
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(iso: string): string {
  const date = parseBackendDate(iso)
  if (Number.isNaN(date.getTime())) return 'unknown date'
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/** Largest unit first — the first one the delta fills is the one we render in. */
const RELATIVE_UNITS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ['year', 365 * 24 * 60 * 60 * 1000],
  ['month', 30 * 24 * 60 * 60 * 1000],
  ['week', 7 * 24 * 60 * 60 * 1000],
  ['day', 24 * 60 * 60 * 1000],
  ['hour', 60 * 60 * 1000],
  ['minute', 60 * 1000],
]

/** "3 hours ago", "yesterday", "just now". */
export function formatRelative(iso: string): string {
  const date = parseBackendDate(iso)
  if (Number.isNaN(date.getTime())) return 'unknown date'

  const deltaMs = date.getTime() - Date.now()
  const magnitude = Math.abs(deltaMs)
  const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

  for (const [unit, unitMs] of RELATIVE_UNITS) {
    if (magnitude >= unitMs) {
      return relative.format(Math.round(deltaMs / unitMs), unit)
    }
  }
  return 'just now'
}

/** Sort key for "newest first" lists. Unparseable dates sink to the bottom. */
export function timestamp(iso: string): number {
  const ms = parseBackendDate(iso).getTime()
  return Number.isNaN(ms) ? -Infinity : ms
}

/** 0.8123 -> "81%" */
export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`
}

/* --- money and quantities ---------------------------------------------------
 *
 * ⚠️ THE RULE THESE ENCODE: a null is NOT a zero. Every money/percent formatter
 * here takes `number | null` and renders null as an em dash, and none of them
 * accepts a fallback argument — so no call site can quietly turn "we could not
 * price this" into "$0.00", which would show a healthy position as a total loss.
 * The em dash (—) is used rather than a hyphen (-) precisely because a hyphen
 * beside a number reads as a minus sign.
 *
 * CURRENCY IS ASSUMED USD. The backend stores no currency — yfinance is fed bare
 * US symbols throughout — so this is correct for the tickers the app supports and
 * would be wrong for a foreign listing. Noted rather than hidden.
 */

/** Rendered in place of any unavailable number. Never "0", never "-". */
export const UNAVAILABLE = '—'

const MONEY = new Intl.NumberFormat(undefined, {
  style: 'currency',
  currency: 'USD',
  // narrowSymbol, or a non-US locale renders every cell as "US$190.00" — en-GB does
  // exactly that. The prefix carries no information here (the app is US-listings
  // only) and costs three characters in every column of a dense table.
  currencyDisplay: 'narrowSymbol',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** 1500 -> "$1,500.00". Null -> "—". */
export function formatMoney(value: number | null): string {
  if (value === null) return UNAVAILABLE
  return MONEY.format(value)
}

/** Always carries its sign, so a gain and a loss are distinguishable without
 *  relying on colour alone. 500 -> "+$500.00", -265 -> "-$265.00". */
export function formatSignedMoney(value: number | null): string {
  if (value === null) return UNAVAILABLE
  // Intl already renders the minus; only a gain needs a sign added.
  return value > 0 ? `+${MONEY.format(value)}` : MONEY.format(value)
}

/** 25 -> "25.00%". Null -> "—". Takes a PERCENT, not a fraction. */
export function formatPercent(value: number | null): string {
  if (value === null) return UNAVAILABLE
  return `${value.toFixed(2)}%`
}

/** 25 -> "+25.00%", -26.5 -> "-26.50%". Null -> "—". */
export function formatSignedPercent(value: number | null): string {
  if (value === null) return UNAVAILABLE
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

/** Share counts. Trailing zeros dropped so a whole number reads as "10", not
 *  "10.0000", while a fractional holding keeps its precision. */
export function formatShares(shares: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(shares)
}

/**
 * Sign of a value, for choosing a colour. Returns null for null AND for zero —
 * flat is not a gain, and colouring 0 green would overstate it.
 */
export function signOf(value: number | null): 'positive' | 'negative' | null {
  if (value === null || value === 0) return null
  return value > 0 ? 'positive' : 'negative'
}
