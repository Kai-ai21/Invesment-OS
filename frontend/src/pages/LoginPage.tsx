import { useState, type FormEvent } from 'react'
import { Loader2 } from 'lucide-react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'

import { AuthLayout, Field, FormError } from '@/components/auth/AuthLayout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { ApiError, NetworkError } from '@/lib/api'

/** Where to go after a successful sign-in, and why it is usually not the dashboard. */
export interface LoginRedirectState {
  /** The route the user was actually trying to reach when they were bounced here. */
  from?: { pathname: string; search?: string; hash?: string }
  /** Set when a session expired underneath them, rather than them arriving here. */
  message?: string
}

export function LoginPage() {
  useDocumentTitle('Log in')
  const navigate = useNavigate()
  const location = useLocation()
  const { login, status } = useAuth()

  const state = (location.state ?? {}) as LoginRedirectState
  // ⚠️ THE POINT OF `from`. Someone who followed a link to /theses/abc123 gets sent
  // here by RequireAuth, and must land back on THAT thesis — not on a dashboard that
  // makes them find it again. Falls back to /theses only when there is nowhere
  // specific to return to.
  const destination = state.from
    ? `${state.from.pathname}${state.from.search ?? ''}${state.from.hash ?? ''}`
    : '/theses'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Already signed in and somehow on this page — a bookmarked /login, or the Back
  // button after logging in. Bounce rather than showing a form that would only
  // re-authenticate the session they already have.
  if (status === 'authenticated') {
    return <Navigate to={destination} replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    // Guards the Enter-key resubmit as well as a second click; the button is
    // disabled too, but a keypress can beat the re-render.
    if (pending) return

    if (!email.trim() || !password) {
      setError('Enter your email and password.')
      return
    }

    setError(null)
    setPending(true)
    try {
      await login(email.trim().toLowerCase(), password)
      navigate(destination, { replace: true })
    } catch (cause: unknown) {
      // ⚠️ THE BACKEND'S OWN WORDING IS USED VERBATIM for a 401, deliberately. It
      // answers "Incorrect email or password." for a wrong password AND for an
      // unknown account — one message, on purpose, so this form cannot be used to
      // discover which email addresses have accounts. Rewriting it here to
      // something friendlier would undo that.
      if (cause instanceof ApiError && cause.status === 401) {
        setError(cause.detail)
      } else if (cause instanceof NetworkError) {
        setError('Could not reach the server. Check your connection and try again.')
      } else if (cause instanceof ApiError) {
        setError(cause.detail)
      } else {
        setError('Something went wrong signing you in. Try again.')
      }
      // The password is deliberately NOT cleared: the usual cause is a typo in the
      // email, and wiping a correctly-typed password punishes the wrong field.
      setPending(false)
    }
  }

  return (
    <AuthLayout
      title="Log in"
      subtitle="Your theses, portfolio and reflections."
      footer={
        <>
          No account yet?{' '}
          <Link
            to="/signup"
            state={state.from ? { from: state.from } : undefined}
            className="rounded-lg text-text-primary underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            Sign up
          </Link>
        </>
      }
    >
      {/* Shown ABOVE the form, before the fields, because it explains why the user
          is looking at a login screen they did not ask for. */}
      {state.message && (
        <p
          role="status"
          className="mb-4 rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-text-secondary"
        >
          {state.message}
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <Field id="email" label="Email">
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            // The one field worth focusing on arrival; there is nothing above it
            // to skip past.
            autoFocus
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={pending}
            className="h-9"
          />
        </Field>

        <Field id="password" label="Password">
          <Input
            id="password"
            name="password"
            type="password"
            // "current-password", not "new-password": tells a password manager to
            // offer what it has rather than to generate something.
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={pending}
            className="h-9"
          />
        </Field>

        {error && <FormError>{error}</FormError>}

        <Button type="submit" disabled={pending} className="mt-2 w-full">
          {pending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Logging in…
            </>
          ) : (
            'Log in'
          )}
        </Button>
      </form>
    </AuthLayout>
  )
}
