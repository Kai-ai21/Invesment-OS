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

/**
 * A DATE-ONLY value ("2026-02-26"), rendered as the calendar date it is.
 *
 * These are not instants. A filing date, or the day someone bought shares, is a
 * date on a calendar with no time and no timezone. Sending one through
 * `formatDate` treats it as UTC midnight and then renders it locally, which is
 * harmless east of Greenwich and WRONG west of it: a filing dated the 26th shows
 * as the 25th in California. Constructing in local time keeps the date put.
 */
export function formatPlainDate(value: string): string {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  // Anything carrying a time is a real instant — hand it back to formatDate.
  if (!parts) return formatDate(value)

  const [, year, month, day] = parts
  const date = new Date(Number(year), Number(month) - 1, Number(day))
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

/** Same ladder as RELATIVE_UNITS, with the suffix each unit abbreviates to. */
const COMPACT_UNITS: Array<[string, number]> = [
  ['y', 365 * 24 * 60 * 60 * 1000],
  ['mo', 30 * 24 * 60 * 60 * 1000],
  ['w', 7 * 24 * 60 * 60 * 1000],
  ['d', 24 * 60 * 60 * 1000],
  ['h', 60 * 60 * 1000],
  ['m', 60 * 1000],
]

/**
 * An age in the fewest characters that still say it: "3h", "2d", "1w", "5mo".
 *
 * For a STATS CELL, where the label above already says what the number is and the
 * column is a quarter of a card wide — "checked 1 week ago" does not fit there and
 * would not be read if it did. Everywhere the sentence fits, formatRelative is
 * still the right one; this is deliberately not a replacement for it.
 *
 * FLOORS rather than rounds, unlike formatRelative. "8 days ago" reads as 1w here
 * and stays 1w until the second week is actually complete, which is what an age
 * counter is expected to do — rounding would tick to 2w at day 11.
 */
export function formatCompactAge(iso: string): string {
  const date = parseBackendDate(iso)
  if (Number.isNaN(date.getTime())) return UNAVAILABLE

  const magnitude = Math.abs(Date.now() - date.getTime())
  for (const [suffix, unitMs] of COMPACT_UNITS) {
    if (magnitude >= unitMs) return `${Math.floor(magnitude / unitMs)}${suffix}`
  }
  return 'now'
}

/**
 * The full instant, for the tooltip behind a relative time: "28 Jul 2026, 02:04 GMT+1".
 *
 * ⚠️ GOES THROUGH parseBackendDate LIKE EVERYTHING ELSE. This is the string that
 * exists to be precise, so it is the one place a raw naive timestamp would do real
 * damage — a reader hovering "2 hours ago" to find out exactly when, and being told
 * a time an hour off, is worse served than by no tooltip at all.
 *
 * The zone name is included deliberately. Once a value is exact to the minute, the
 * next question is "in whose time?", and every timestamp in this app has already
 * been converted out of UTC into the viewer's local zone.
 */
export function formatExact(iso: string): string {
  const date = parseBackendDate(iso)
  if (Number.isNaN(date.getTime())) return 'unknown date'
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  })
}

/**
 * The corrected instant as a machine-readable UTC string, for a <time> element's
 * `dateTime`. Empty when unparseable, so the attribute can be omitted entirely
 * rather than carrying "Invalid Date".
 */
export function toMachineDate(iso: string): string {
  const date = parseBackendDate(iso)
  return Number.isNaN(date.getTime()) ? '' : date.toISOString()
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

/**
 * Large sums at a glance: 3_240_000_000_000 -> "$3.24T". Null -> "—".
 *
 * Market caps are compared against each other, not reconciled against a ledger, so
 * three significant figures is the useful precision — "$3,240,187,441,152" is
 * harder to rank by eye and implies an accuracy the figure does not have. Falls
 * through to plain money below a million, where the abbreviation stops helping.
 */
export function formatCompactMoney(value: number | null): string {
  if (value === null) return UNAVAILABLE

  const scales: Array<[number, string]> = [
    [1e12, 'T'],
    [1e9, 'B'],
    [1e6, 'M'],
  ]
  const magnitude = Math.abs(value)
  for (const [size, suffix] of scales) {
    if (magnitude >= size) {
      const scaled = value / size
      // Two decimals under 100 ("$3.24T"), one above ("$142.6B") — keeps the string
      // a predictable width so a column of them stays scannable.
      const digits = Math.abs(scaled) >= 100 ? 1 : 2
      return `$${scaled.toFixed(digits)}${suffix}`
    }
  }
  return formatMoney(value)
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
