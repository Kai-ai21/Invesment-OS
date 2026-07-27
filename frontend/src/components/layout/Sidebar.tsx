import {
  Bell,
  List,
  Newspaper,
  NotebookPen,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react'
import { NavLink } from 'react-router'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// `badge` names which count decorates the item, so adding a badged nav item is a
// data change rather than another branch in the render.
const NAV_ITEMS = [
  { to: '/theses', label: 'Theses', icon: List, badge: null },
  { to: '/alerts', label: 'Alerts', icon: Bell, badge: 'unread' },
  { to: '/reflections', label: 'Reflections', icon: NotebookPen, badge: 'pending' },
] as const

/** Shared by the NavLinks and by the News trigger, which is a button rather than a
 *  link — it opens a panel over the current page instead of navigating. Extracted so
 *  the two never drift apart. */
function navItemClasses(collapsed: boolean, active: boolean) {
  return cn(
    'flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors',
    'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
    collapsed && 'justify-center px-0',
    active
      ? 'bg-surface-raised text-text-primary'
      : 'text-text-secondary hover:bg-surface-raised/60 hover:text-text-primary',
  )
}

export function Sidebar({
  collapsed,
  onToggle,
  unreadCount,
  pendingReflections,
  onOpenNews,
  newsOpen,
}: {
  collapsed: boolean
  onToggle: () => void
  unreadCount: number
  pendingReflections: number
  onOpenNews: () => void
  newsOpen: boolean
}) {
  const counts = { unread: unreadCount, pending: pendingReflections }
  return (
    <aside
      className={cn(
        'glass-chrome relative z-10 flex h-full shrink-0 flex-col gap-6 border-r py-4 transition-[width] duration-200',
        collapsed ? 'w-16 px-2' : 'w-60 px-3',
      )}
    >
      {/* Wordmark. The mark stays put when collapsed so nothing jumps. */}
      <div className={cn('flex items-center gap-2.5', collapsed && 'justify-center')}>
        <div
          aria-hidden
          className="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-raised text-xs font-semibold text-text-primary"
        >
          IO
        </div>
        {/* Wordmark in the display font, weight 400 (no font-medium — Righteous
            is single-weight and would otherwise be synthetically bolded). */}
        {!collapsed && (
          <span className="truncate font-display text-sm tracking-[0.01em] text-text-primary">
            Investment OS
          </span>
        )}
      </div>

      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon, badge: badgeKey }) => {
          const count = badgeKey ? counts[badgeKey] : 0
          const badge = count > 0 ? count : null
          // Alerts are "unread"; reflections are "pending". Announcing three
          // reflections as "3 unread" would be simply wrong.
          const badgeNoun = badgeKey === 'pending' ? 'pending' : 'unread'

          return (
            <NavLink
              key={to}
              to={to}
              title={
                collapsed
                  ? badge
                    ? `${label} (${badge} ${badgeNoun})`
                    : label
                  : undefined
              }
              className={({ isActive }) => navItemClasses(collapsed, isActive)}
            >
              <span className="relative shrink-0">
                <Icon className="size-4" aria-hidden />
                {/* Collapsed to an icon rail there's no room for the count, so
                    it degrades to a dot; the tooltip still carries the number. */}
                {badge !== null && collapsed && (
                  <span
                    aria-hidden
                    className="absolute -top-0.5 -right-0.5 size-1.5 rounded-full bg-text-primary"
                  />
                )}
              </span>

              {!collapsed && (
                <>
                  <span className="truncate">{label}</span>
                  {/* bg-background, not surface-raised — the active nav item is
                      already surface-raised and would swallow it. */}
                  {badge !== null && (
                    <span className="ml-auto min-w-5 rounded-4xl bg-background px-1.5 py-0.5 text-center text-xs text-text-primary">
                      {badge}
                    </span>
                  )}
                </>
              )}

              {badge !== null && (
                <span className="sr-only">
                  {badge} {badgeNoun}
                </span>
              )}
            </NavLink>
          )
        })}

        {/* A button, not a NavLink: News opens a slide-over on top of whatever page
            you are on rather than navigating away. The /news route still exists and
            the panel's "See all" goes there. */}
        <button
          type="button"
          onClick={onOpenNews}
          title={collapsed ? 'News' : undefined}
          aria-haspopup="dialog"
          aria-expanded={newsOpen}
          className={navItemClasses(collapsed, newsOpen)}
        >
          <Newspaper className="size-4 shrink-0" aria-hidden />
          {!collapsed && <span className="truncate">News</span>}
        </button>
      </nav>

      <div className={cn('mt-auto', collapsed ? 'flex justify-center' : '')}>
        {/* Secondary rather than muted: against the glass panel #6b7280
            measures 2.9:1, below AA-large. */}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onToggle}
          aria-expanded={!collapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="text-text-secondary hover:text-text-primary"
        >
          {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
        </Button>
      </div>
    </aside>
  )
}
