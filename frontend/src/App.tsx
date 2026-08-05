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
                  {/* ⚠️ THE BOUNDARY IS THE ROUTE ELEMENT, WRAPPING AppShell rather
                      than sitting inside it. React unmounts the whole root on an
                      uncaught error, so what matters is that SOMETHING above the
                      crash survives to render a fallback — and the shell itself
                      (sidebar, ambient background) is as capable of throwing as any
                      page inside it. Placed here, the providers, the router and the
                      transition all stay mounted and the user gets a message.

                      The trade this accepts: a crash in one PAGE takes the shell's
                      chrome down with it, because the boundary is above both. A
                      second boundary around <Outlet /> would keep the nav usable,
                      and is the obvious next move if page-level crashes ever become
                      common enough to be worth the extra component. One is the
                      difference between a black screen and a message; the second is
                      a refinement on top of that. */}
                  <Route
                    element={
                      <ErrorBoundary>
                        <AppShell />
                      </ErrorBoundary>
                    }
                  >
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
        </TooltipProvider>
      </ToastProvider>
    </AuthProvider>
  )
}

export default App
