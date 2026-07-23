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
