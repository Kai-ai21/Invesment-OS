import { useState } from 'react'
import { Outlet } from 'react-router'

import { Sidebar } from '@/components/layout/Sidebar'

/**
 * Persistent chrome around every route. Because this is a layout route, the
 * collapsed state lives here and survives navigation — deliberately in React
 * state only, so it resets on reload.
 */
export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1100px] px-10 py-10">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
