import { useCallback, useEffect, useState } from 'react'
import { Outlet } from 'react-router'

import { Sidebar } from '@/components/layout/Sidebar'
import type { ShellContext } from '@/hooks/useShellContext'
import { listAlerts } from '@/lib/api'

/**
 * Persistent chrome around every route. Because this is a layout route, the
 * collapsed state lives here and survives navigation — deliberately in React
 * state only, so it resets on reload.
 */
export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)

  // Fetched once on mount and again whenever a page reports a change. The badge
  // is decoration, so a failure here stays silent rather than breaking the shell.
  const refreshUnreadCount = useCallback(async () => {
    try {
      setUnreadCount((await listAlerts(true)).length)
    } catch {
      setUnreadCount(0)
    }
  }, [])

  useEffect(() => {
    void refreshUnreadCount()
  }, [refreshUnreadCount])

  const context: ShellContext = { refreshUnreadCount }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
        unreadCount={unreadCount}
      />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1100px] px-10 py-10">
          <Outlet context={context} />
        </div>
      </main>
    </div>
  )
}
