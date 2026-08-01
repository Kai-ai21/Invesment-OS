import { useCallback, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router'

import { DashboardBackground } from '@/components/effects/DashboardBackground'
import { usePageLeaving } from '@/components/layout/PageTransition'
import { Sidebar } from '@/components/layout/Sidebar'
import { NewsPanel } from '@/components/news/NewsPanel'
import type { ShellContext } from '@/hooks/useShellContext'
import { listAlerts, listPostMortems } from '@/lib/api'
import { cn } from '@/lib/utils'

/**
 * Persistent chrome around every route. Because this is a layout route, the
 * collapsed state lives here and survives navigation — deliberately in React
 * state only, so it resets on reload.
 */
export function AppShell() {
  // The HELD location — inside PageTransition's <Routes location=…> this is the
  // route actually on screen, which is what the key below must follow.
  const location = useLocation()
  const leaving = usePageLeaving()
  const [collapsed, setCollapsed] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [pendingReflections, setPendingReflections] = useState(0)
  // React state only — the panel is a transient view, not a preference to persist.
  const [newsOpen, setNewsOpen] = useState(false)
  // Stable identity: NewsPanel's focus effect depends on it, and a new function each
  // render would re-run that effect and keep pulling focus back into the panel.
  const closeNews = useCallback(() => setNewsOpen(false), [])

  // Fetched once on mount and again whenever a page reports a change. The badge
  // is decoration, so a failure here stays silent rather than breaking the shell.
  const refreshUnreadCount = useCallback(async () => {
    try {
      setUnreadCount((await listAlerts(true)).length)
    } catch {
      setUnreadCount(0)
    }
  }, [])

  // Same contract as the alert badge: fetched on mount, re-fetched only when a page
  // reports a change. Decoration, so a failure stays silent.
  const refreshPendingReflections = useCallback(async () => {
    try {
      setPendingReflections((await listPostMortems(true)).length)
    } catch {
      setPendingReflections(0)
    }
  }, [])

  useEffect(() => {
    void refreshUnreadCount()
    void refreshPendingReflections()
  }, [refreshUnreadCount, refreshPendingReflections])

  const context: ShellContext = { refreshUnreadCount, refreshPendingReflections }

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
        pendingReflections={pendingReflections}
        onOpenNews={() => setNewsOpen(true)}
        newsOpen={newsOpen}
      />
      <main className="relative z-10 flex-1 overflow-y-auto">
        {/* Keyed on the path so the entry animation replays on every route
            change. While `leaving` the key has NOT changed yet — this is still
            the outgoing page, and it swaps its entry animation for the exit one
            on the element already in place. */}
        <div
          key={location.pathname}
          className={cn(
            leaving ? 'page-leave' : 'page-enter',
            'mx-auto max-w-[1100px] px-10 py-10',
          )}
        >
          <Outlet context={context} />
        </div>
      </main>

      {/* Mounted only while open, so the panel fetches on open and its focus
          effect runs exactly once per opening. */}
      {newsOpen && <NewsPanel onClose={closeNews} />}
    </div>
  )
}
