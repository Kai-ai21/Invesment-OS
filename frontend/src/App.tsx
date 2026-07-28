import { Navigate, Route, Routes } from 'react-router'

import { AppShell } from '@/components/layout/AppShell'
import { AlertsPage } from '@/pages/AlertsPage'
import { LandingPage } from '@/pages/LandingPage'
import { NewsPage } from '@/pages/NewsPage'
import { ReflectionsPage } from '@/pages/ReflectionsPage'
import { NewThesisPage } from '@/pages/NewThesisPage'
import { PortfolioPage } from '@/pages/PortfolioPage'
import { ThesesPage } from '@/pages/ThesesPage'
import { ThesisDetailPage } from '@/pages/ThesisDetailPage'

function App() {
  return (
    <Routes>
      {/* Landing sits outside the shell — no sidebar, and the particle field
          never renders behind the dashboard. */}
      <Route path="/" element={<LandingPage />} />

      <Route element={<AppShell />}>
        <Route path="theses" element={<ThesesPage />} />
        {/* "new" is declared before ":id" for readability; React Router ranks
            static segments above dynamic ones regardless of order. */}
        <Route path="theses/new" element={<NewThesisPage />} />
        <Route path="theses/:id" element={<ThesisDetailPage />} />
        <Route path="portfolio" element={<PortfolioPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="news" element={<NewsPage />} />
        <Route path="reflections" element={<ReflectionsPage />} />
        <Route path="*" element={<Navigate to="/theses" replace />} />
      </Route>
    </Routes>
  )
}

export default App
