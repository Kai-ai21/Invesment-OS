import { Loader2 } from 'lucide-react'
import { Navigate, Outlet, useLocation } from 'react-router'

import { useAuth } from '@/hooks/useAuth'

/**
 * The gate on everything inside the shell. A layout route, so it wraps the whole
 * authenticated section rather than being remembered per page — a route added inside
 * it is protected by position, which is the only kind of protection nobody forgets.
 */
export function RequireAuth() {
  const { status, expiredMessage } = useAuth()
  const location = useLocation()

  if (status === 'checking') {
    return <CheckingSession />
  }

  if (status === 'anonymous') {
    return (
      // ⚠️ `state.from` IS THE WHOLE REQUIREMENT, and it is why this cannot be a
      // plain <Navigate to="/login" />. Someone opening a link to
      // /theses/abc123 — from an alert email, a bookmark, a message — must land on
      // THAT thesis after logging in, not on a dashboard that makes them find it
      // again. The location object is passed whole so the query string and hash
      // survive too.
      //
      // `replace` so /login does not become a history entry: pressing Back from
      // the page they land on after logging in should leave the app, not return
      // them to a login screen they have already satisfied.
      // `message` is set only when the server ended the session underneath them
      // (see AuthContext) — a plain anonymous visitor gets no explanation because
      // there is nothing to explain. This is the ONE place an anonymous user is
      // sent to /login, so the message cannot be lost to a competing redirect.
      <Navigate
        to="/login"
        replace
        state={{ from: location, message: expiredMessage ?? undefined }}
      />
    )
  }

  return <Outlet />
}

/**
 * What "checking" looks like.
 *
 * ⚠️ NEITHER THE DASHBOARD NOR THE LOGIN FORM. Rendering either would be guessing
 * at the answer the /auth/me call is about to give, and being wrong half the time
 * is what produces the flash this state exists to prevent.
 *
 * Deliberately plain: no sidebar, no ambient background, nothing that belongs to a
 * signed-in session, because this may resolve to anonymous. The delay is one request
 * against localhost, so this is usually a single frame — the spinner is faded in on
 * a delay so a fast check shows nothing at all rather than a flicker of its own.
 */
function CheckingSession() {
  return (
    <div
      className="flex h-screen items-center justify-center bg-background"
      // Announced politely rather than assertively: this is a transient state, and
      // it must not interrupt whatever a screen reader is currently saying.
      role="status"
      aria-live="polite"
      data-testid="auth-checking"
    >
      <span className="flex items-center gap-2.5 text-sm text-text-secondary opacity-0 [animation:fade-in-delayed_200ms_ease-out_150ms_forwards]">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Checking your session…
      </span>
    </div>
  )
}
