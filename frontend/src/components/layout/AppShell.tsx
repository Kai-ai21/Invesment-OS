import { useCallback, useEffect, useState } from 'react'
import { Menu } from 'lucide-react'
import { Outlet, useLocation } from 'react-router'

import { DashboardBackground } from '@/components/effects/DashboardBackground'
import { usePageLeaving } from '@/components/layout/PageTransition'
import { Sidebar } from '@/components/layout/Sidebar'
import { NewsPanel } from '@/components/news/NewsPanel'
import { Button } from '@/components/ui/button'
import type { ShellContext } from '@/hooks/useShellContext'
import { useNarrowViewport } from '@/hooks/useMediaQuery'
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
  // ⚠️ A WIDTH QUERY, NOT A POINTER ONE, and the difference is the point. The
  // background asks about the INPUT DEVICE because a comet needs a cursor to chase;
  // the sidebar asks about AVAILABLE ROOM because 240px of permanent chrome is the
  // problem whether a mouse or a thumb is driving. A 12" tablet gets the full
  // sidebar and the static backdrop; a laptop window dragged narrow gets the drawer
  // and keeps the comet. Conflating the two would get both of those backwards.
  const narrow = useNarrowViewport()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])
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

      {/* The drawer's only opener. Fixed rather than in the page flow so it does
          not scroll away from a reader halfway down a long list — reaching the nav
          should never cost a scroll to the top. z-40 keeps it above the drawer
          itself, so the same control closes what it opened. */}
      {narrow && (
        <Button
          variant="secondary"
          size="icon-sm"
          onClick={() => setDrawerOpen((open) => !open)}
          aria-expanded={drawerOpen}
          aria-label={drawerOpen ? 'Close navigation' : 'Open navigation'}
          // Solid, overriding the variant's translucent glass: this floats over
          // whatever happens to be scrolling under it, and a see-through control
          // sitting on top of body text is the one place translucency costs more
          // than it gives.
          className="fixed top-3 left-3 z-40 border-border bg-surface-raised backdrop-blur-none"
        >
          <Menu aria-hidden />
        </Button>
      )}

      <Sidebar
        // Never collapsed in drawer mode: the drawer is either open with full
        // labels or gone, and an icon rail is not one of its two states.
        collapsed={narrow ? false : collapsed}
        onToggle={() => setCollapsed((c) => !c)}
        unreadCount={unreadCount}
        pendingReflections={pendingReflections}
        onOpenNews={() => {
          setNewsOpen(true)
          setDrawerOpen(false)
        }}
        newsOpen={newsOpen}
        drawer={narrow}
        drawerOpen={drawerOpen}
        onDrawerClose={closeDrawer}
      />
      <main className="scroll-stable relative z-10 flex-1 overflow-y-auto">
        {/* Keyed on the path so the entry animation replays on every route
            change. While `leaving` the key has NOT changed yet — this is still
            the outgoing page, and it swaps its entry animation for the exit one
            on the element already in place. */}
        <div
          key={location.pathname}
          className={cn(
            leaving ? 'page-leave' : 'page-enter',
            // ⚠️ THE PADDING IS PART OF THE NARROW-VIEWPORT FIX, not a tidy-up.
            // A flat px-12 is 96px of margin on a 390px phone — a quarter of the
            // screen spent on whitespace, on top of whatever the sidebar took.
            // Freeing the sidebar's 240px and then keeping desktop padding would
            // have solved half the problem.
            // pt-16 on narrow clears the fixed menu button, which would otherwise
            // sit on top of every page's <h1>.
            'mx-auto max-w-[1100px] px-5 pt-16 pb-8 sm:px-8 lg:px-12 lg:pt-12 lg:pb-12',
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
