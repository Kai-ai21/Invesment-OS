import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useNavigate } from 'react-router'

import {
  getMe,
  login as loginRequest,
  signup as signupRequest,
  type User,
} from '@/lib/api'
import {
  SESSION_EXPIRED_MESSAGE,
  clearToken,
  readToken,
  setExpiryListener,
  writeToken,
} from '@/lib/authToken'

/**
 * ⚠️ THREE STATES, NOT TWO, AND THE THIRD ONE IS THE WHOLE POINT.
 *
 * On the first paint after a reload the app holds a token string and knows nothing
 * about whether it still works — the answer needs a round trip to /auth/me. Modelled
 * as a boolean, that moment has to be called something, and both answers are wrong:
 *
 *   default anonymous → every reload flashes the login screen for ~100ms before the
 *                       dashboard replaces it, on every page, forever;
 *   default authed    → the dashboard renders, fires its requests, they 401, and the
 *                       user is thrown to /login having briefly seen their data.
 *
 * "checking" is the honest answer, and it is a state the UI can render deliberately
 * (see RequireAuth) rather than a lie it has to recover from.
 */
export type AuthStatus = 'checking' | 'authenticated' | 'anonymous'

export interface AuthContextValue {
  status: AuthStatus
  user: User | null
  token: string | null
  /**
   * Set only when a session was ENDED BY THE SERVER mid-use, rather than the user
   * arriving signed-out. RequireAuth passes it to /login so the redirect explains
   * itself; null for someone who simply is not logged in, who needs no explanation.
   */
  expiredMessage: string | null
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()

  // Seeded from storage so the very first render already knows whether there is
  // anything to validate — with no token there is nothing to check, and going
  // straight to "anonymous" avoids a pointless request and a pointless spinner.
  const [token, setToken] = useState<string | null>(() => readToken())
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<AuthStatus>(() =>
    readToken() === null ? 'anonymous' : 'checking',
  )

  const [expiredMessage, setExpiredMessage] = useState<string | null>(null)

  /**
   * ⚠️ THE MOUNT CHECK IS WHAT MAKES "checking" RESOLVE. A token in localStorage
   * proves only that we stored one — it may be expired, it may be signed by a
   * backend whose JWT_SECRET has since rotated, or its account may have been
   * deleted. /auth/me is the only thing that actually knows.
   */
  useEffect(() => {
    const stored = readToken()
    if (stored === null) {
      setStatus('anonymous')
      return
    }

    let cancelled = false
    void (async () => {
      try {
        const me = await getMe()
        if (cancelled) return
        setUser(me)
        setToken(stored)
        setStatus('authenticated')
      } catch {
        // Any failure resolves to anonymous, INCLUDING a network error. The
        // alternative is sitting in "checking" behind a spinner with no way out
        // when the backend is down; landing on /login at least renders something
        // and lets them retry. The token is cleared on a 401 by api.ts; a network
        // failure deliberately leaves it alone, so a reload once the backend is
        // back signs them straight in.
        if (cancelled) return
        setUser(null)
        setStatus('anonymous')
      }
    })()

    return () => {
      cancelled = true
    }
    // Mount only. Re-running this on navigation would re-validate on every page
    // change, which is a request per click to learn something already known.
  }, [])

  /**
   * What happens when the API reports our token is no longer accepted.
   *
   * api.ts has already cleared the token by the time this runs — see
   * handleUnauthorized. This part is the app's response: drop the session and
   * record WHY, so the redirect can explain itself.
   *
   * ⚠️ IT DOES NOT NAVIGATE, AND THAT IS A FIX RATHER THAN AN OMISSION. It used to,
   * and the navigation lost a race it could not win: flipping status to "anonymous"
   * makes RequireAuth render its own <Navigate to="/login"> in the same commit, and
   * that redirect — which carries `from` but knew nothing about any message —
   * replaced this one. The result was a silent bounce to a login screen with no
   * explanation, which is exactly the "Error: 401 is useless to the user" outcome
   * this was written to prevent, arrived at from the other direction.
   *
   * So there is now ONE place that decides where an anonymous user goes, and it
   * reads the message from here.
   */
  useEffect(() => {
    setExpiryListener(() => {
      setToken(null)
      setUser(null)
      setStatus('anonymous')
      setExpiredMessage(SESSION_EXPIRED_MESSAGE)
    })
    return () => setExpiryListener(null)
  }, [])

  /** Shared by login and signup — both end with a token and a user. */
  const establishSession = useCallback(async (accessToken: string) => {
    writeToken(accessToken)
    setToken(accessToken)
    // Cleared on the way IN, so a later manual logout does not redirect carrying a
    // stale "your session expired" from an hour ago.
    setExpiredMessage(null)
    // Fetched rather than decoded from the JWT: the token carries only a `sub`,
    // and the email shown in the sidebar should come from the server's answer
    // rather than from a payload the client parsed for itself.
    const me = await getMe()
    setUser(me)
    setStatus('authenticated')
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await loginRequest(email, password)
      await establishSession(access_token)
    },
    [establishSession],
  )

  const signup = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await signupRequest(email, password)
      await establishSession(access_token)
    },
    [establishSession],
  )

  const logout = useCallback(() => {
    // Local only: the backend issues stateless JWTs and keeps no session to end,
    // so "logging out" IS discarding the token. The token stays technically valid
    // until it expires, which is the accepted cost of stateless auth and the
    // reason ACCESS_TOKEN_EXPIRE_MINUTES is worth keeping short.
    clearToken()
    setToken(null)
    setUser(null)
    setStatus('anonymous')
    // Nothing expired — they chose this, so there is nothing to explain.
    setExpiredMessage(null)
    // No `from`: a deliberate exit, so coming back should not silently return them
    // to whatever page they chose to leave.
    navigate('/login', { replace: true })
  }, [navigate])

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, token, expiredMessage, login, signup, logout }),
    [status, user, token, expiredMessage, login, signup, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
