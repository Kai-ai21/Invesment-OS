/**
 * The access token, and the one signal that says it stopped working.
 *
 * ⚠️ THIS MODULE EXISTS TO BREAK A CYCLE, not because the token deserves a file.
 * api.ts must attach the token and react to a 401; AuthContext must call api.ts to
 * log in and validate. If the token lived in the context, those two would import
 * each other. A leaf module both can depend on is the cheapest way out — and it
 * keeps `localStorage` reachable from exactly one place, so there is one spelling of
 * the key rather than four.
 */

/**
 * ⚠️ localStorage, KNOWINGLY, AND THE TRADE IS REAL.
 *
 * A token in localStorage is readable by any script that runs on this origin, so a
 * single XSS hole is a full account takeover with a 24-hour lifetime — and unlike a
 * session cookie, nothing about it expires when the tab closes. The alternative is an
 * httpOnly, SameSite cookie the browser attaches automatically and JavaScript cannot
 * read at all, which is strictly safer and costs a CSRF defence, a cookie-aware CORS
 * setup, and a backend that reads credentials from two places during the migration.
 *
 * This is a single-user app on a laptop, not publicly exposed, with no third-party
 * scripts and no user-generated HTML rendered anywhere. The realistic XSS surface is
 * a compromised npm dependency, which on this deployment would have far worse avenues
 * than a stolen token. So: localStorage, deliberately, with the reasoning written
 * down rather than discovered later.
 *
 * ⚠️ IF THIS APP IS EVER DEPLOYED SOMEWHERE PUBLIC, OR GETS A SECOND USER, revisit
 * this first. The change is contained: this file, plus the backend reading the
 * cookie. Nothing else touches the token.
 */
const STORAGE_KEY = 'investment-os.access-token'

/** What the user is told when their token stopped being accepted. */
export const SESSION_EXPIRED_MESSAGE = 'Your session expired. Please log in again.'

export function readToken(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    // Safari in private mode, and any browser with storage disabled, throw on
    // access rather than returning null. Treated as "no token": the user gets the
    // login screen and a working (if unremembered) session, instead of a blank app.
    return null
  }
}

export function writeToken(token: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, token)
  } catch {
    // Same reasoning. The token stays in memory for this page's lifetime because
    // the context holds it too, so the session works and simply does not survive
    // a reload.
  }
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* nothing to clear if we could never write */
  }
}

/**
 * Called when the API rejects our token. Set by AuthContext.
 *
 * ⚠️ A CALLBACK RATHER THAN A REDIRECT FROM INSIDE api.ts. The fetch helper has no
 * business calling `window.location = '/login'`: that is a full page reload, it
 * discards React state that a form may still need, and it makes api.ts untestable
 * without a router. The helper reports the fact; the context decides what it means.
 */
type ExpiryListener = () => void

let onExpired: ExpiryListener | null = null

export function setExpiryListener(listener: ExpiryListener | null): void {
  onExpired = listener
}

/**
 * Clear the token and tell the app. Safe to call repeatedly — several in-flight
 * requests will all 401 together when a token expires, and the second one through
 * must not undo the first one's work or fire a second redirect.
 */
export function handleUnauthorized(): void {
  const hadToken = readToken() !== null
  clearToken()
  if (hadToken) onExpired?.()
}
