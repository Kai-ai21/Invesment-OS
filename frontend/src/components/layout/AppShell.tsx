import { useCallback, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router'

import { DashboardBackground } from '@/components/effects/DashboardBackground'
import { Sidebar } from '@/components/layout/Sidebar'
import type { ShellContext } from '@/hooks/useShellContext'
import { listAlerts } from '@/lib/api'

/**
 * Persistent chrome around every route. Because this is a layout route, the
 * collapsed state lives here and survives navigation — deliberately in React
 * state only, so it resets on reload.
 */
export function AppShell() {
  const location = useLocation()
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
    <div className="relative flex h-screen overflow-hidden bg-background">
      {/* Two ambient layers the glass chrome refracts, both fixed to the
          viewport at z-0 and painted before the z-10 sidebar/content. Order
          matters: the animated cursor light is the FIRST child, so among the
          equal z-0 layers it sits lowest; the static blobs paint over it and
          give the glass something to refract even when the cursor is idle.
          Both are pointer-transparent and additive-only, so opaque content
          above is never dimmed. Landing has its own field and gets neither. */}
      <DashboardBackground />
      <div aria-hidden className="ambient-backdrop pointer-events-none fixed inset-0 z-0" />

      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
        unreadCount={unreadCount}
      />
      <main className="relative z-10 flex-1 overflow-y-auto">
        {/* Keyed on the path so the fade replays on every route change. */}
        <div
          key={location.pathname}
          className="page-enter mx-auto max-w-[1100px] px-10 py-10"
        >
          <Outlet context={context} />
        </div>
      </main>
    </div>
  )
}
