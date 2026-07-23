import { Navigate, Route, Routes } from 'react-router'

import { AppShell } from '@/components/layout/AppShell'
import { AlertsPage } from '@/pages/AlertsPage'
import { NewThesisPage } from '@/pages/NewThesisPage'
import { ThesesPage } from '@/pages/ThesesPage'
import { ThesisDetailPage } from '@/pages/ThesisDetailPage'

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/theses" replace />} />
        <Route path="theses" element={<ThesesPage />} />
        {/* "new" is declared before ":id" for readability; React Router ranks
            static segments above dynamic ones regardless of order. */}
        <Route path="theses/new" element={<NewThesisPage />} />
        <Route path="theses/:id" element={<ThesisDetailPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="*" element={<Navigate to="/theses" replace />} />
      </Route>
    </Routes>
  )
}

export default App
