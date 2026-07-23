import { Bell, List, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { NavLink } from 'react-router'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/theses', label: 'Theses', icon: List },
  { to: '/alerts', label: 'Alerts', icon: Bell },
] as const

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean
  onToggle: () => void
}) {
  return (
    <aside
      className={cn(
        'flex h-full shrink-0 flex-col gap-6 border-r border-border bg-surface py-4 transition-[width] duration-200',
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
        {!collapsed && (
          <span className="truncate font-heading text-sm font-medium text-text-primary">
            Investment OS
          </span>
        )}
      </div>

      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors',
                'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                collapsed && 'justify-center px-0',
                isActive
                  ? 'bg-surface-raised text-text-primary'
                  : 'text-text-secondary hover:bg-surface-raised/60 hover:text-text-primary',
              )
            }
          >
            <Icon className="size-4 shrink-0" aria-hidden />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className={cn('mt-auto', collapsed ? 'flex justify-center' : '')}>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onToggle}
          aria-expanded={!collapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="text-text-muted hover:text-text-primary"
        >
          {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
        </Button>
      </div>
    </aside>
  )
}
