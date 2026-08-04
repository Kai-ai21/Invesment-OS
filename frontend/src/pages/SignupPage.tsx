import { useState, type FormEvent } from 'react'
import { Loader2 } from 'lucide-react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'

import { AuthLayout, Field, FormError } from '@/components/auth/AuthLayout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { ApiError, NetworkError } from '@/lib/api'
import type { LoginRedirectState } from '@/pages/LoginPage'

/**
 * ⚠️ THESE RULES MIRROR THE BACKEND'S, and the mirroring is the contract.
 * SignupRequest in backend/api/schemas.py enforces the same three, and IT is the
 * authority — this exists so the user finds out before a round trip, not so the
 * server can trust the client. A rule changed on one side must be changed here too;
 * the failure mode otherwise is a 422 rendered as a raw validation blob.
 */
const MIN_PASSWORD_LENGTH = 8
/** bcrypt hashes at most 72 BYTES, and the backend rejects more. Bytes, not
 *  characters: 40 accented characters are 80 bytes in UTF-8. */
const MAX_PASSWORD_BYTES = 72

/** Deliberately permissive. Full RFC 5322 is not worth implementing client-side and
 *  a strict pattern rejects addresses that genuinely work; the server does the real
 *  check. This only catches the obvious typo — a missing @, a missing dot. */
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function SignupPage() {
  useDocumentTitle('Sign up')
  const navigate = useNavigate()
  const location = useLocation()
  const { signup, status } = useAuth()

  const state = (location.state ?? {}) as LoginRedirectState
  const destination = state.from
    ? `${state.from.pathname}${state.from.search ?? ''}${state.from.hash ?? ''}`
    : '/theses'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (status === 'authenticated') {
    return <Navigate to={destination} replace />
  }

  function validate(): string | null {
    const trimmed = email.trim()
    if (!trimmed) return 'Enter your email.'
    if (!EMAIL_PATTERN.test(trimmed)) return 'That does not look like an email address.'
    if (!password) return 'Choose a password.'
    if (password.length < MIN_PASSWORD_LENGTH) {
      return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`
    }
    if (new TextEncoder().encode(password).length > MAX_PASSWORD_BYTES) {
      return `Password is too long — at most ${MAX_PASSWORD_BYTES} bytes. Accented and non-Latin characters count as more than one each.`
    }
    // Checked LAST, so a password that is too short says so rather than the
    // confirm field complaining about a mismatch the user is still typing.
    if (password !== confirmPassword) return 'The two passwords do not match.'
    return null
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return

    const problem = validate()
    if (problem) {
      setError(problem)
      return
    }

    setError(null)
    setPending(true)
    try {
      await signup(email.trim().toLowerCase(), password)
      navigate(destination, { replace: true })
    } catch (cause: unknown) {
      if (cause instanceof ApiError && cause.status === 409) {
        // The one place the app DOES confirm an account exists — unavoidable, since
        // the whole answer is "you cannot have this address". Login stays silent
        // about it, which is where enumeration would actually matter.
        setError('An account with that email already exists. Log in instead.')
      } else if (cause instanceof ApiError && cause.status === 403) {
        // ALLOW_SIGNUP=false on the backend.
        setError(cause.detail)
      } else if (cause instanceof NetworkError) {
        setError('Could not reach the server. Check your connection and try again.')
      } else if (cause instanceof ApiError) {
        setError(cause.detail)
      } else {
        setError('Something went wrong creating your account. Try again.')
      }
      setPending(false)
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="One account holds your theses, portfolio and reflections."
      footer={
        <>
          Already have an account?{' '}
          <Link
            to="/login"
            state={state.from ? { from: state.from } : undefined}
            className="rounded-lg text-text-primary underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <Field id="email" label="Email">
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            autoFocus
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={pending}
            className="h-9"
          />
        </Field>

        <Field
          id="password"
          label="Password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
        >
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={pending}
            className="h-9"
          />
        </Field>

        <Field id="confirm-password" label="Confirm password">
          <Input
            id="confirm-password"
            name="confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            disabled={pending}
            className="h-9"
          />
        </Field>

        {error && <FormError>{error}</FormError>}

        <Button type="submit" disabled={pending} className="mt-2 w-full">
          {pending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Creating your account…
            </>
          ) : (
            'Create account'
          )}
        </Button>
      </form>
    </AuthLayout>
  )
}
