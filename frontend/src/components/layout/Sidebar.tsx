import {
  Bell,
  ChartCandlestick,
  List,
  Newspaper,
  NotebookPen,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Wallet,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useEffect } from 'react'
import { NavLink, useLocation } from 'react-router'

import { LogoMark } from '@/components/LogoMark'
import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/tooltip'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

interface NavItem {
  /** Route to navigate to, or null for News — a panel trigger, not a link. */
  to: string | null
  label: string
  icon: LucideIcon
  /** Names which count decorates the item, so adding a badged nav item is a data
   *  change rather than another branch in the render. */
  badge: 'unread' | 'pending' | null
}

/**
 * THE NAV, GROUPED BY WHAT THE PAGES ARE FOR — not by how often they're used.
 * Track is the user's own reasoning, Explore is the outside world, Own is what
 * they hold. The order is that arc and is deliberate: your thinking first, the
 * world it's about second, the consequence last.
 */
const SECTIONS: { id: string; label: string; items: readonly NavItem[] }[] = [
  {
    id: 'track',
    label: 'Track',
    items: [
      { to: '/theses', label: 'Theses', icon: List, badge: null },
      { to: '/alerts', label: 'Alerts', icon: Bell, badge: 'unread' },
      { to: '/reflections', label: 'Reflections', icon: NotebookPen, badge: 'pending' },
    ],
  },
  {
    id: 'explore',
    label: 'Explore',
    items: [
      { to: '/market', label: 'Market', icon: ChartCandlestick, badge: null },
      // News has no `to`: it opens a slide-over on top of whatever page you are
      // on rather than navigating away. The /news route still exists and the
      // panel's "See all" goes there.
      { to: null, label: 'News', icon: Newspaper, badge: null },
      // Research lives at /research/:ticker — it is always ABOUT something, and
      // there is no index to link to. Left out rather than shipped as a nav item
      // that cannot go anywhere; it belongs behind a ticker search.
    ],
  },
  {
    id: 'own',
    label: 'Own',
    items: [{ to: '/portfolio', label: 'Portfolio', icon: Wallet, badge: null }],
  },
]

/** Shared by the NavLinks and by the News trigger, which is a button rather than a
 *  link — it opens a panel over the current page instead of navigating. Extracted so
 *  the two never drift apart. */
function navItemClasses(collapsed: boolean, active: boolean) {
  return cn(
    'flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors',
    'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
    collapsed && 'justify-center px-0',
    active
      ? 'bg-surface-raised text-text-primary'
      : 'text-text-secondary hover:bg-surface-raised/60 hover:text-text-primary',
  )
}

/**
 * ⚠️ WHY THE ACTIVE STATE IS COMPUTED HERE rather than left to NavLink's own
 * `({ isActive }) => …` render prop.
 *
 * Collapsed, each item is wrapped in a Tooltip, whose Radix trigger renders
 * `asChild` — and Slot MERGES className by string-concatenating its own with the
 * child's. A function does not survive that: it arrives at NavLink already
 * stringified, NavLink takes its string branch, and the item renders with no
 * classes at all — no padding, no hit target, no active fill. Expanded there is
 * no tooltip and no Slot, which is why it only ever went wrong on the rail.
 *
 * Passing a plain string sidesteps the merge entirely. Same matching rule
 * NavLink uses: the exact path, or a descendant of it (/theses/:id keeps Theses
 * lit), with the trailing slash stripped so `/theses` cannot match `/thesesX`.
 */
function isActivePath(pathname: string, to: string) {
  const base = to.replace(/\/$/, '')
  return pathname === base || pathname.startsWith(`${base}/`)
}

/** The inside of a nav item — identical whether the outside is a link or a button,
 *  which is the whole point of pulling it out. */
function NavItemBody({
  label,
  icon: Icon,
  badge,
  badgeNoun,
  collapsed,
}: {
  label: string
  icon: LucideIcon
  badge: number | null
  badgeNoun: string
  collapsed: boolean
}) {
  return (
    <>
      <span className="relative shrink-0">
        <Icon className="size-4" aria-hidden />
        {/* Collapsed to an icon rail there's no room for the count, so it
            degrades to a dot; the tooltip still carries the number. */}
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
          {/* bg-background, not surface-raised — the active nav item is already
              surface-raised and would swallow it. */}
          {badge !== null && (
            <span className="ml-auto min-w-5 rounded-full bg-background px-1.5 py-0.5 text-center text-xs tabular-nums text-text-primary">
              {badge}
            </span>
          )}
        </>
      )}

      {/* Collapsed, this is the item's ONLY accessible name — the tooltip is
          decoration and screen readers never see it. */}
      {collapsed && <span className="sr-only">{label}</span>}

      {badge !== null && (
        <span className="sr-only">
          {badge} {badgeNoun}
        </span>
      )}
    </>
  )
}

/**
 * The group heading: a short bright dash, then the name in the same mono/upper/
 * tracked language as the status badges. PRIMARY text, not muted — at 9.5px a
 * muted label reads as disabled rather than as structure.
 *
 * aria-hidden, and deliberately so: the grouping reaches screen readers through
 * the aria-label on each <ul> (a named list), which announces on entry and does
 * not leave a stray heading in the document outline.
 */
function SectionLabel({ label }: { label: string }) {
  return (
    <div aria-hidden className="mb-[7px] flex items-center gap-[7px] px-2.5">
      <span className="h-0.5 w-2.5 shrink-0 rounded-full bg-text-primary" />
      <span className="font-mono text-[9.5px] leading-none tracking-[0.14em] text-text-primary uppercase">
        {label}
      </span>
    </div>
  )
}

export function Sidebar({
  collapsed,
  onToggle,
  unreadCount,
  pendingReflections,
  onOpenNews,
  newsOpen,
  drawer = false,
  drawerOpen = false,
  onDrawerClose,
}: {
  collapsed: boolean
  onToggle: () => void
  unreadCount: number
  pendingReflections: number
  onOpenNews: () => void
  newsOpen: boolean
  /** Narrow viewport: render as an off-canvas drawer rather than a column. */
  drawer?: boolean
  /** Drawer only — whether it is currently slid in. */
  drawerOpen?: boolean
  /** Drawer only — dismiss, for the scrim, Escape, and following a nav link. */
  onDrawerClose?: () => void
}) {
  const counts = { unread: unreadCount, pending: pendingReflections }
  const { pathname } = useLocation()

  // Escape closes the drawer. Bound only while it is open, so nothing listens on a
  // desktop layout where there is no drawer to dismiss.
  useEffect(() => {
    if (!drawer || !drawerOpen || !onDrawerClose) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onDrawerClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [drawer, drawerOpen, onDrawerClose])

  return (
    <>
      {/* Scrim. Drawer only, and only while open — it both dims the page and gives
          the "tap outside to dismiss" gesture something to land on. */}
      {drawer && (
        <div
          aria-hidden
          onClick={onDrawerClose}
          className={cn(
            'fixed inset-0 z-20 bg-black/60 transition-opacity duration-200',
            drawerOpen ? 'opacity-100' : 'pointer-events-none opacity-0',
          )}
        />
      )}

      <aside
        // ⚠️ INERT WHEN CLOSED, not merely translated off-screen. A drawer parked at
        // -100% is still in the accessibility tree and still focusable: tabbing from
        // the page would walk into six invisible nav links. `inert` takes the whole
        // subtree out of focus order and out of the a11y tree in one attribute.
        //
        // Passed as a real boolean, not `inert=""`. React 19 treats `inert` as a
        // boolean prop and drops an empty string as falsy — which silently produced
        // no attribute at all, i.e. exactly the focus trap this line exists to stop.
        inert={drawer && !drawerOpen}
        className={cn(
          'flex h-full flex-col border-r py-4',
          drawer
            ? [
                // Fixed and above the scrim, so it slides OVER the content rather
                // than displacing it — the content column keeps the full viewport
                // width at every drawer state.
                'glass-chrome glass-chrome-solid fixed inset-y-0 left-0 z-30 w-64 px-3',
                'transition-transform duration-200 will-change-transform',
                drawerOpen ? 'translate-x-0' : '-translate-x-full',
              ]
            : [
                'glass-chrome relative z-10 shrink-0 transition-[width] duration-200',
                collapsed ? 'w-16 px-2' : 'w-60 px-3',
              ],
        )}
      >
      {/* Wordmark. The mark stays put when collapsed so nothing jumps. */}
      <div
        className={cn('flex shrink-0 items-center gap-2.5', collapsed && 'justify-center')}
      >
        <div
          aria-hidden
          className="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-raised text-text-primary"
        >
          <LogoMark />
        </div>
        {/* Wordmark in the display font, weight 400 (no font-medium — Righteous
            is single-weight and would otherwise be synthetically bolded). */}
        {!collapsed && (
          <span className="truncate font-display text-sm tracking-[0.01em] text-text-primary">
            Kailaas OS
          </span>
        )}
      </div>

      {/* flex-1 + min-h-0 is what pins the footer: the nav absorbs the slack at a
          tall viewport and gives it back at a short one, scrolling internally
          rather than pushing the footer off the bottom.
          The -mx-1/px-1 pair buys 4px of bleed so the 3px focus ring is not
          clipped by the scroll container — overflow-y:auto forces the x axis to
          clip too, however much room the aside's own padding looks like it has. */}
      <nav
        aria-label="Main"
        className="mt-6 -mx-1 min-h-0 flex-1 overflow-y-auto px-1"
      >
        {SECTIONS.map((section, index) => (
          <div key={section.id} className={cn(index > 0 && 'mt-3')}>
            {/* Collapsed there is no room for a label, so the grouping survives
                as a rule between the rails. Screen readers keep the real thing
                either way — see SectionLabel. */}
            {collapsed
              ? index > 0 && (
                  <hr aria-hidden className="mx-auto mb-3 w-6 border-t border-border" />
                )
              : <SectionLabel label={section.label} />}

            <ul aria-label={section.label} className="flex flex-col gap-1">
              {section.items.map(({ to, label, icon, badge: badgeKey }) => {
                const count = badgeKey ? counts[badgeKey] : 0
                const badge = count > 0 ? count : null
                // Alerts are "unread"; reflections are "pending". Announcing
                // three reflections as "3 unread" would be simply wrong.
                const badgeNoun = badgeKey === 'pending' ? 'pending' : 'unread'
                const body = (
                  <NavItemBody
                    label={label}
                    icon={icon}
                    badge={badge}
                    badgeNoun={badgeNoun}
                    collapsed={collapsed}
                  />
                )

                return (
                  <li key={label}>
                    {/* Collapsed, the rail is icons alone and the tooltip carries
                        the only label there is — so it replaces the native
                        `title`, which waits about a second, cannot be reached by
                        keyboard, and renders in the OS style rather than this
                        one. */}
                    <Tooltip
                      side="right"
                      content={
                        collapsed
                          ? badge
                            ? `${label} — ${badge} ${badgeNoun}`
                            : label
                          : null
                      }
                    >
                      {to === null ? (
                        <button
                          type="button"
                          onClick={onOpenNews}
                          aria-haspopup="dialog"
                          aria-expanded={newsOpen}
                          className={navItemClasses(collapsed, newsOpen)}
                        >
                          {body}
                        </button>
                      ) : (
                        <NavLink
                          to={to}
                          // Following a link dismisses the drawer. Without this it
                          // would stay open over the page it just navigated to,
                          // which on a phone means arriving somewhere you cannot
                          // see — the drawer covers most of the viewport.
                          onClick={onDrawerClose}
                          className={navItemClasses(
                            collapsed,
                            isActivePath(pathname, to),
                          )}
                        >
                          {body}
                        </NavLink>
                      )}
                    </Tooltip>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Utility footer. The hairline is what anchors the column — below it the
          sidebar ends, rather than fading into whatever space is left.
          Search (⌘K) and Settings belong here too, and are left out until there
          is a command palette and a settings page to open: a row that does
          nothing when clicked reads as broken, not as forthcoming. */}
      <div className="mt-4 shrink-0 border-t border-border pt-3">
        <AccountBlock collapsed={collapsed} />

        {/* The collapse control is a DESKTOP affordance and is not rendered in the
            drawer. Collapsing a drawer to an icon rail would leave a 64px strip
            floating over the page, which is neither open nor closed; the drawer's
            two states are its whole interface, and it is dismissed by the scrim,
            Escape, the menu button, or following a link. */}
        {!drawer && (
          <div className={cn('mt-1', collapsed && 'flex justify-center')}>
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
        )}
      </div>
      </aside>
    </>
  )
}


/**
 * Who is signed in, and the way out.
 *
 * The email is MUTED AND SMALL on purpose: it answers "which account is this"
 * for someone who has more than one, and is otherwise the least interesting
 * text on the screen. Sizing it like a nav item would give an identity label
 * the same weight as the things the app is actually for.
 */
function AccountBlock({ collapsed }: { collapsed: boolean }) {
  const { user, logout } = useAuth()

  return (
    <div className={cn('flex flex-col gap-1', collapsed && 'items-center')}>
      {/* Truncated rather than wrapped: a long address must not grow the footer
          and push the nav's scroll area around. The title attribute is the escape
          hatch for reading the whole thing. */}
      {!collapsed && user && (
        <p
          className="truncate px-2.5 text-xs text-text-muted"
          title={user.email}
        >
          {user.email}
        </p>
      )}

      <Tooltip side="right" content={collapsed ? `Log out${user ? ` (${user.email})` : ''}` : null}>
        <button
          type="button"
          onClick={logout}
          className={cn(
            'flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors',
            'text-text-secondary hover:bg-surface-raised/60 hover:text-text-primary',
            'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
            collapsed && 'justify-center px-0',
          )}
        >
          <LogOut className="size-4 shrink-0" aria-hidden />
          {!collapsed && <span className="truncate">Log out</span>}
          {collapsed && <span className="sr-only">Log out</span>}
        </button>
      </Tooltip>
    </div>
  )
}
