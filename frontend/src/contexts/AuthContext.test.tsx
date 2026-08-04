import { useEffect } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'

import { RequireAuth } from '@/components/auth/RequireAuth'
import { AuthProvider } from '@/contexts/AuthContext'
import { ToastProvider } from '@/components/ui/toast'
import { TooltipProvider } from '@/components/ui/tooltip'
import { LoginPage } from '@/pages/LoginPage'
import { listTheses } from '@/lib/api'

const STORAGE_KEY = 'investment-os.access-token'
const API_BASE = 'http://127.0.0.1:8000'

/**
 * Resolves only when the test says so, so the "checking" state can be OBSERVED
 * rather than raced past. Without this, /auth/me settles in the same tick and the
 * three-state machine is untestable — which is precisely how a two-state one gets
 * shipped by accident.
 */
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** The real app's provider stack, in the real order, around a route table. */
function renderApp(initialEntries: string[] = ['/theses']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <AuthProvider>
        <ToastProvider>
          <TooltipProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<RequireAuth />}>
                <Route path="/theses" element={<div>Dashboard</div>} />
                <Route path="/theses/:id" element={<ThesisProbe />} />
              </Route>
            </Routes>
          </TooltipProvider>
        </ToastProvider>
      </AuthProvider>
    </MemoryRouter>,
  )
}

/** Fires an authenticated request on mount, the way every real page does. */
function ExpiringPage() {
  useEffect(() => {
    void listTheses().catch(() => {})
  }, [])
  return <div>Portfolio</div>
}

/** Reports the route it was rendered at, so redirect destinations are assertable. */
function ThesisProbe() {
  const location = useLocation()
  return <div>Thesis page at {location.pathname}</div>
}

beforeEach(() => {
  window.localStorage.clear()
  vi.restoreAllMocks()
})

afterEach(() => {
  window.localStorage.clear()
})

describe('the three states', () => {
  it('renders NEITHER the dashboard nor the login form while checking', async () => {
    // Arrange — a stored token whose validation has not come back yet.
    window.localStorage.setItem(STORAGE_KEY, 'a-stored-token')
    const pending = deferred<Response>()
    vi.spyOn(globalThis, 'fetch').mockReturnValue(pending.promise)

    // Act
    renderApp()

    // Assert — the whole point of the third state. Showing either one here would
    // be guessing at an answer that has not arrived, and being wrong half the time
    // is the flash this exists to prevent.
    expect(await screen.findByTestId('auth-checking')).toBeInTheDocument()
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /log in/i })).not.toBeInTheDocument()

    // Cleanup — let the pending request settle so React is not left mid-update.
    pending.resolve(jsonResponse({ id: 'u1', email: 'ada@example.com' }))
    await waitFor(() => expect(screen.getByText('Dashboard')).toBeInTheDocument())
  })

  it('resolves an INVALID stored token to anonymous and shows the login form', async () => {
    // Arrange — a token that looks fine to us and is rejected by the server. This
    // is why "we have a token" cannot stand in for "we are signed in".
    window.localStorage.setItem(STORAGE_KEY, 'an-expired-or-forged-token')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse({ detail: 'Not authenticated.' }, 401),
    )

    // Act
    renderApp()

    // Assert
    expect(await screen.findByRole('button', { name: /^log in$/i })).toBeInTheDocument()
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()
    expect(screen.queryByTestId('auth-checking')).not.toBeInTheDocument()
  })

  it('resolves a VALID stored token to authenticated', async () => {
    window.localStorage.setItem(STORAGE_KEY, 'a-good-token')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse({ id: 'u1', email: 'ada@example.com' }),
    )

    renderApp()

    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
  })

  it('goes straight to anonymous with NO stored token, without calling the API', async () => {
    // Arrange — nothing to validate, so a request would be asking a question whose
    // answer is already known.
    const fetchMock = vi.spyOn(globalThis, 'fetch')

    // Act
    renderApp()

    // Assert
    expect(await screen.findByRole('button', { name: /^log in$/i })).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('the global 401 handler', () => {
  it('CLEARS THE TOKEN when a request comes back 401', async () => {
    // Arrange
    window.localStorage.setItem(STORAGE_KEY, 'a-token-that-just-expired')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse({ detail: 'Not authenticated.' }, 401),
    )

    // Act — any endpoint; the handling lives in the shared helper, not the caller.
    await expect(listTheses()).rejects.toThrow()

    // Assert — a token the server refuses is worse than no token: it keeps the app
    // believing it has a session and re-failing every request behind it.
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('attaches the bearer token to every request from the ONE shared helper', async () => {
    window.localStorage.setItem(STORAGE_KEY, 'a-good-token')
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse([]))

    await listTheses()

    const [, init] = fetchMock.mock.calls[0]
    expect((init?.headers as Record<string, string>).Authorization).toBe(
      'Bearer a-good-token',
    )
  })

  it('does NOT clear the token on a non-401 failure', async () => {
    // A 500 is the server's problem, not the session's. Logging the user out over
    // it would turn a transient backend fault into a lost session.
    window.localStorage.setItem(STORAGE_KEY, 'a-good-token')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse({ detail: 'boom' }, 500),
    )

    await expect(listTheses()).rejects.toThrow()

    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('a-good-token')
  })

  it('sends NO token on login, so a stale one cannot trip the 401 handler', async () => {
    // Arrange — the failure this prevents: an expired token in storage, the user
    // typing their password, and the login request itself firing "session expired".
    window.localStorage.setItem(STORAGE_KEY, 'a-stale-token')
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse({ access_token: 't', token_type: 'bearer' }))

    const { login } = await import('@/lib/api')
    await login('ada@example.com', 'password')

    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toBe(`${API_BASE}/auth/login`)
    expect((init?.headers as Record<string, string>).Authorization).toBeUndefined()
    // And the stale token is still there — login must not clear it as a side effect.
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('a-stale-token')
  })
})

describe('a session that expires mid-use', () => {
  it('redirects to login AND SAYS WHY', async () => {
    // ⚠️ REGRESSION TEST FOR A BUG THIS SUITE ORIGINALLY MISSED. The expiry handler
    // used to navigate to /login itself, carrying the message — and lost a race it
    // could not win: setting status to "anonymous" makes RequireAuth render its own
    // <Navigate>, which replaced the one with the message. The user was bounced to a
    // bare login screen with no explanation, which is the exact outcome the global
    // 401 handling exists to prevent. Caught in the browser, not here.
    //
    // Now a single redirect carries both, and this test would fail if that were
    // ever split back apart.
    window.localStorage.setItem(STORAGE_KEY, 'a-token-that-expires-mid-session')

    let meCalls = 0
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/auth/me')) {
        meCalls += 1
        // Valid on mount, so the app settles into "authenticated"...
        if (meCalls === 1) return jsonResponse({ id: 'u1', email: 'ada@example.com' })
      }
      // ...and every subsequent request 401s, as a real expiry does.
      return jsonResponse({ detail: 'Not authenticated.' }, 401)
    })

    render(
      <MemoryRouter initialEntries={['/portfolio']}>
        <AuthProvider>
          <ToastProvider>
            <TooltipProvider>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route element={<RequireAuth />}>
                  <Route path="/portfolio" element={<ExpiringPage />} />
                </Route>
              </Routes>
            </TooltipProvider>
          </ToastProvider>
        </AuthProvider>
      </MemoryRouter>,
    )

    // The page loads, then its own request 401s underneath the user.
    await screen.findByText('Portfolio')

    // Assert — at /login, and the reason is on screen. "Error: 401" is what this
    // replaces.
    expect(
      await screen.findByText('Your session expired. Please log in again.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^log in$/i })).toBeInTheDocument()
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('shows NO expiry message to someone who was simply never logged in', async () => {
    // There is nothing to explain to a first-time visitor, and telling them their
    // session expired would be a small lie.
    renderApp(['/theses'])

    await screen.findByRole('button', { name: /^log in$/i })
    expect(screen.queryByText(/session expired/i)).not.toBeInTheDocument()
  })
})

describe('the post-login redirect', () => {
  it('RETURNS THE USER TO THE ROUTE THEY ORIGINALLY ASKED FOR', async () => {
    // Arrange — someone opens a link to a specific thesis while signed out.
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/auth/login')) {
        return jsonResponse({ access_token: 'fresh-token', token_type: 'bearer' })
      }
      if (url.endsWith('/auth/me')) {
        return jsonResponse({ id: 'u1', email: 'ada@example.com' })
      }
      return jsonResponse([])
    })

    renderApp(['/theses/abc123'])

    // Bounced to login, because there is no session.
    await screen.findByRole('button', { name: /^log in$/i })
    expect(screen.queryByText(/Thesis page/)).not.toBeInTheDocument()

    // Act
    await user.type(screen.getByLabelText(/email/i), 'ada@example.com')
    await user.type(screen.getByLabelText(/password/i), 'a-real-password')
    await user.click(screen.getByRole('button', { name: /^log in$/i }))

    // Assert — /theses/abc123, NOT the dashboard. Landing on /theses here would
    // mean the link they followed was silently discarded.
    expect(await screen.findByText('Thesis page at /theses/abc123')).toBeInTheDocument()
  })

  it('falls back to the dashboard when there was no particular destination', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/auth/login')) {
        return jsonResponse({ access_token: 'fresh-token', token_type: 'bearer' })
      }
      if (url.endsWith('/auth/me')) {
        return jsonResponse({ id: 'u1', email: 'ada@example.com' })
      }
      return jsonResponse([])
    })

    renderApp(['/login'])

    await user.type(screen.getByLabelText(/email/i), 'ada@example.com')
    await user.type(screen.getByLabelText(/password/i), 'a-real-password')
    await user.click(screen.getByRole('button', { name: /^log in$/i }))

    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
  })
})

describe('the login form', () => {
  it('shows the server wording inline on bad credentials, and does not clear the password', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse({ detail: 'Incorrect email or password.' }, 401),
    )

    renderApp(['/login'])

    await user.type(screen.getByLabelText(/email/i), 'ada@example.com')
    await user.type(screen.getByLabelText(/password/i), 'wrong-password')
    await user.click(screen.getByRole('button', { name: /^log in$/i }))

    // Inline and announced, not a toast that vanishes on a timer.
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Incorrect email or password.')
    // The usual cause is a mistyped EMAIL; wiping the password punishes the wrong
    // field.
    expect(screen.getByLabelText(/password/i)).toHaveValue('wrong-password')
  })

  it('cannot be double-submitted while a request is in flight', async () => {
    const user = userEvent.setup()
    const pending = deferred<Response>()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(pending.promise)

    renderApp(['/login'])

    await user.type(screen.getByLabelText(/email/i), 'ada@example.com')
    await user.type(screen.getByLabelText(/password/i), 'a-real-password')
    const submit = screen.getByRole('button', { name: /^log in$/i })
    await user.click(submit)

    // Disabled while pending, so a second click does nothing.
    await waitFor(() => expect(screen.getByRole('button', { name: /logging in/i })).toBeDisabled())
    await user.click(screen.getByRole('button', { name: /logging in/i }))

    expect(fetchMock).toHaveBeenCalledTimes(1)

    pending.resolve(jsonResponse({ detail: 'Incorrect email or password.' }, 401))
    await screen.findByRole('alert')
  })
})
