import { Navigate, Route, Routes } from 'react-router'

import { RequireAuth } from '@/components/auth/RequireAuth'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { AppShell } from '@/components/layout/AppShell'
import { PageTransition } from '@/components/layout/PageTransition'
import { ToastProvider } from '@/components/ui/toast'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AuthProvider } from '@/contexts/AuthContext'
import { AlertsPage } from '@/pages/AlertsPage'
import { LandingPage } from '@/pages/LandingPage'
import { LoginPage } from '@/pages/LoginPage'
import { MarketPage } from '@/pages/MarketPage'
import { NewsPage } from '@/pages/NewsPage'
import { ReflectionsPage } from '@/pages/ReflectionsPage'
import { NewThesisPage } from '@/pages/NewThesisPage'
import { PortfolioPage } from '@/pages/PortfolioPage'
import { ResearchPage } from '@/pages/ResearchPage'
import { SignupPage } from '@/pages/SignupPage'
import { ThesesPage } from '@/pages/ThesesPage'
import { ThesisDetailPage } from '@/pages/ThesisDetailPage'

function App() {
  return (
    // ⚠️ AuthProvider IS OUTSIDE PageTransition, and has to be. It navigates on
    // session expiry and holds the session itself — inside the transition it would
    // be remounted by the route changes it causes, re-running the /auth/me check on
    // every navigation and dropping the user mid-redirect.
    //
    // The two UI providers stay outside the transition for their own reasons: a
    // toast raised by an action on one page is not torn down by navigating away
    // from it, and the tooltip delay is shared across the app rather than
    // restarting per route.
    <AuthProvider>
      <ToastProvider>
        <TooltipProvider>
          {/* ⚠️ THE BOUNDARY WRAPS EVERY ROUTE, NOT JUST THE SHELL. It first went
              in around <AppShell> alone, which left the landing page, the login
              form and the signup form outside it — so a crash on any of the three
              screens a signed-out visitor can actually reach still unmounted the
              root and painted the page black. That is the wrong half of the app to
              protect: those are the screens a first-time visitor sees.

              Here it covers the whole route table while staying INSIDE the three
              providers, which is what lets the fallback render as part of a working
              app rather than replacing all of it. Above PageTransition rather than
              below, so a crash thrown while a route is being swapped — the shape of
              the bug this was added for — is caught too. */}
          <ErrorBoundary>
          {/* The route table is matched against the location PageTransition is
              holding, which lags the real one by the length of the outgoing fade.
              See the notes there — this is what lets the page being left render
              itself out. */}
          <PageTransition>
            {(location) => (
              <Routes location={location}>
                {/* PUBLIC. The landing page sits outside the shell — no sidebar,
                    and the particle field never renders behind the dashboard. It
                    fetches nothing, so it works signed out. */}
                <Route path="/" element={<LandingPage />} />

                {/* PUBLIC, and necessarily so: these are how you stop being
                    anonymous. Outside AppShell too — the shell's badge fetches
                    would 401 for someone who is not signed in yet. */}
                <Route path="login" element={<LoginPage />} />
                <Route path="signup" element={<SignupPage />} />

                {/* ⚠️ EVERYTHING BELOW IS BEHIND RequireAuth, BY POSITION RATHER
                    THAN BY REMEMBERING. A route added inside this element is
                    protected because of where it sits — the only kind of
                    protection nobody forgets. Same reasoning as the backend's A3
                    audit, where three endpoints had been missed by hand. */}
                <Route element={<RequireAuth />}>
                  <Route element={<AppShell />}>
                    <Route path="theses" element={<ThesesPage />} />
                    {/* "new" is declared before ":id" for readability; React Router
                        ranks static segments above dynamic ones regardless of order. */}
                    <Route path="theses/new" element={<NewThesisPage />} />
                    <Route path="theses/:id" element={<ThesisDetailPage />} />
                    <Route path="portfolio" element={<PortfolioPage />} />
                    <Route path="market" element={<MarketPage />} />
                    <Route path="research/:ticker" element={<ResearchPage />} />
                    <Route path="alerts" element={<AlertsPage />} />
                    <Route path="news" element={<NewsPage />} />
                    <Route path="reflections" element={<ReflectionsPage />} />
                    <Route path="*" element={<Navigate to="/theses" replace />} />
                  </Route>
                </Route>
              </Routes>
            )}
          </PageTransition>
          </ErrorBoundary>
        </TooltipProvider>
      </ToastProvider>
    </AuthProvider>
  )
}

export default App
