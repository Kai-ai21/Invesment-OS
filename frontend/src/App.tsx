import { Navigate, Route, Routes } from 'react-router'

import { AppShell } from '@/components/layout/AppShell'
import { PageTransition } from '@/components/layout/PageTransition'
import { ToastProvider } from '@/components/ui/toast'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AlertsPage } from '@/pages/AlertsPage'
import { LandingPage } from '@/pages/LandingPage'
import { MarketPage } from '@/pages/MarketPage'
import { NewsPage } from '@/pages/NewsPage'
import { ReflectionsPage } from '@/pages/ReflectionsPage'
import { NewThesisPage } from '@/pages/NewThesisPage'
import { PortfolioPage } from '@/pages/PortfolioPage'
import { ResearchPage } from '@/pages/ResearchPage'
import { ThesesPage } from '@/pages/ThesesPage'
import { ThesisDetailPage } from '@/pages/ThesisDetailPage'

function App() {
  return (
    // Both providers sit OUTSIDE the transition, so a toast raised by an action
    // on one page is not torn down by navigating away from it, and the tooltip
    // delay is shared across the whole app rather than restarting per route.
    <ToastProvider>
      <TooltipProvider>
        {/* The route table is matched against the location PageTransition is
            holding, which lags the real one by the length of the outgoing fade.
            See the notes there — this is what lets the page being left render
            itself out. */}
        <PageTransition>
          {(location) => (
            <Routes location={location}>
              {/* Landing sits outside the shell — no sidebar, and the particle
                  field never renders behind the dashboard. */}
              <Route path="/" element={<LandingPage />} />

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
            </Routes>
          )}
        </PageTransition>
      </TooltipProvider>
    </ToastProvider>
  )
}

export default App
