import { ApiError, NetworkError } from '@/lib/api'

/**
 * ⚠️ THE ONE PLACE A FAILURE BECOMES SOMETHING A PERSON CAN READ.
 *
 * Every error surface used to render `error.message` directly, and those messages
 * are written for a developer reading a stack trace. What users actually saw:
 *
 *   "/theses failed (500): Internal Server Error"
 *   "/news/NVDA failed (422): [{"type":"greater_than_equal","loc":["query",...
 *   "Could not reach the API at http://127.0.0.1:8000/theses. Is the backend running?"
 *
 * A path, a status code, a JSON blob, and a localhost URL — none of which tells
 * someone what broke or whether pressing the button again is worth their time.
 *
 * So nothing rendered to a user reads `.message` any more; it goes through here.
 * The rule for every string below: say WHAT failed, and say whether retrying helps.
 * Never a status code, never a URL, never JSON.
 */
export interface ErrorCopy {
  /** Headline — what failed, named in the user's terms. */
  title: string
  /** What happened, and what to do about it. */
  detail: string
  /**
   * False when trying again cannot possibly help — a missing record, a rejected
   * input. The caller hides its Retry button rather than offering an action that
   * is guaranteed to fail again.
   */
  canRetry: boolean
}

/**
 * `subject` is a noun phrase naming what the user was trying to see, and lands in
 * the title: "your theses", "this thesis", "the market data". Lowercase, no
 * article-free abbreviations — it is read as part of a sentence.
 */
export function describeError(cause: unknown, subject: string): ErrorCopy {
  if (cause instanceof NetworkError) {
    return {
      title: `Couldn't reach the server`,
      detail:
        "The app can't reach its backend right now. Check that you're online, then try again — nothing you've saved is affected.",
      canRetry: true,
    }
  }

  if (cause instanceof ApiError) {
    return describeApiError(cause, subject)
  }

  // Anything else is a bug on our side rather than a condition of the request, so
  // it gets an honest generic rather than a guess at a cause.
  return {
    title: `Couldn't load ${subject}`,
    detail: 'Something went wrong in the app. Reloading the page usually clears it.',
    canRetry: true,
  }
}

function describeApiError(error: ApiError, subject: string): ErrorCopy {
  // 404: the backend's own 404 wording is already plain and specific — "Thesis not
  // found", "No company found for NVDA" — so it is passed through rather than
  // replaced with something vaguer.
  if (error.status === 404) {
    return {
      title: 'Not found',
      detail: `${stripTrailingStop(error.detail)}. It may have been deleted, or the link may be wrong.`,
      canRetry: false,
    }
  }

  if (error.status === 422) {
    return {
      title: `Couldn't accept that`,
      detail: describeValidation(error),
      canRetry: false,
    }
  }

  if (error.status === 429) {
    return {
      title: 'Too many requests',
      detail:
        'The data provider is rate-limiting us. Wait a minute or so, then try again.',
      canRetry: true,
    }
  }

  // 502/503/504 mean an UPSTREAM failed — the SEC, the price feed, the news feed —
  // not this app. The backend's detail for these carries an exception repr
  // ("...: ConnectTimeout()"), so it is deliberately not surfaced.
  if (error.status === 502 || error.status === 503 || error.status === 504) {
    return {
      title: `Couldn't load ${subject}`,
      detail:
        "The market data provider isn't responding. That's usually brief — try again in a moment.",
      canRetry: true,
    }
  }

  if (error.status >= 500) {
    return {
      title: `Couldn't load ${subject}`,
      detail: 'Something went wrong on our end. Trying again often works.',
      canRetry: true,
    }
  }

  return {
    title: `Couldn't load ${subject}`,
    detail: `${stripTrailingStop(error.detail)}.`,
    canRetry: false,
  }
}

/**
 * FastAPI reports request-validation failures as an ARRAY of objects, and
 * `JSON.stringify`ing that is how a user came to be shown
 * `[{"type":"greater_than_equal","loc":["query","limit"],...}]`.
 *
 * Unpacked into sentences instead. `loc` is a path like ["body","shares"]; its
 * LAST element is the field name, and the leading "body"/"query" is dropped
 * because it describes our transport, not anything the user typed.
 *
 * Our own hand-written 422s (`raise HTTPException(422, detail="...")`) send a
 * plain string and are shown as-is — those are already written for a person.
 */
function describeValidation(error: ApiError): string {
  let parsed: unknown
  try {
    parsed = JSON.parse(error.body)
  } catch {
    return 'That input was rejected. Check the values and try again.'
  }

  const detail = (parsed as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return `${stripTrailingStop(detail)}.`
  if (!Array.isArray(detail)) {
    return 'That input was rejected. Check the values and try again.'
  }

  const problems = detail
    .map((item) => {
      const entry = item as { loc?: unknown[]; msg?: unknown }
      const message = typeof entry.msg === 'string' ? entry.msg : null
      if (!message) return null
      const field = Array.isArray(entry.loc)
        ? entry.loc.filter((part) => typeof part === 'string' && part !== 'body' && part !== 'query').pop()
        : null
      return field ? `${humanise(String(field))}: ${lowerFirst(message)}` : message
    })
    .filter((item): item is string => item !== null)

  if (problems.length === 0) {
    return 'That input was rejected. Check the values and try again.'
  }
  return `${problems.join('. ')}.`
}

/** "average_cost" -> "Average cost". */
function humanise(field: string): string {
  const words = field.replace(/[_-]+/g, ' ').trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

function lowerFirst(text: string): string {
  // Only when the second character is lowercase, so "SEC is unavailable" and other
  // acronyms are left alone.
  if (text.length > 1 && text[1] === text[1].toLowerCase()) {
    return text.charAt(0).toLowerCase() + text.slice(1)
  }
  return text
}

/** So a detail that already ends in a stop doesn't get a second one appended. */
function stripTrailingStop(text: string): string {
  return text.trim().replace(/[.!?]+$/, '')
}
