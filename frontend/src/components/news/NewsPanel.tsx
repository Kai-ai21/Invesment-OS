import { useEffect, useId, useRef } from 'react'
import { Loader2, RefreshCw, X } from 'lucide-react'
import { Link } from 'react-router'

import { NewsList } from '@/components/news/NewsList'
import { Button } from '@/components/ui/button'
import { useNews } from '@/hooks/useNews'

/** How many headlines the panel shows before "See all" takes over. */
const PANEL_ITEM_LIMIT = 15

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Right-hand slide-over. Mounted only while open, so `onClose` MUST be stable
 * (useCallback in the parent) — an unstable identity would re-run the focus effect
 * on every render and keep stealing focus back to the top of the panel.
 */
export function NewsPanel({ onClose }: { onClose: () => void }) {
  const { items, loading, error, refreshing, refresh, reload } = useNews()
  const panelRef = useRef<HTMLDivElement>(null)
  const headingId = useId()

  useEffect(() => {
    // Captured before we move focus, and restored on unmount — that is what returns
    // focus to the sidebar trigger when the panel closes, without the parent having
    // to pass a ref down.
    const previouslyFocused = document.activeElement as HTMLElement | null

    const focusable = () =>
      Array.from(panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])

    // Focus the first control, or the panel itself if it somehow has none — either
    // way focus must land inside the dialog, never behind it.
    const firstFocusable = focusable()[0]
    if (firstFocusable) {
      firstFocusable.focus()
    } else {
      panelRef.current?.focus()
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
        return
      }
      if (event.key !== 'Tab') return

      // Focus trap: wrap at both ends so Tab can never reach the page behind.
      const elements = focusable()
      if (elements.length === 0) {
        event.preventDefault()
        return
      }
      const first = elements[0]
      const last = elements[elements.length - 1]
      const active = document.activeElement

      if (event.shiftKey && (active === first || !panelRef.current?.contains(active))) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      previouslyFocused?.focus()
    }
  }, [onClose])

  return (
    <>
      {/* Backdrop. aria-hidden because the dialog itself carries the semantics; it
          exists to dim the page and to catch outside clicks. */}
      <div
        aria-hidden
        onClick={onClose}
        className="fixed inset-0 z-40 bg-background/60 animate-in fade-in duration-200 motion-reduce:animate-none"
      />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        tabIndex={-1}
        className="glass-chrome fixed inset-y-0 right-0 z-50 flex w-[420px] max-w-full flex-col border-l outline-none animate-in slide-in-from-right duration-200 motion-reduce:animate-none"
      >
        <header className="flex items-center gap-2 border-b border-border px-6 py-4">
          <h2
            id={headingId}
            className="font-display text-xl tracking-[0.01em] text-text-primary"
          >
            News
          </h2>
          {refreshing && (
            <Loader2 className="size-3.5 animate-spin text-text-secondary" aria-hidden />
          )}

          <div className="ml-auto flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={refresh}
              disabled={refreshing}
              aria-label="Refresh news"
              className="text-text-secondary hover:text-text-primary"
            >
              <RefreshCw aria-hidden />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onClose}
              aria-label="Close news panel"
              className="text-text-secondary hover:text-text-primary"
            >
              <X aria-hidden />
            </Button>
          </div>
        </header>

        <div className="scroll-stable flex-1 overflow-y-auto px-6">
          <NewsList
            items={items.slice(0, PANEL_ITEM_LIMIT)}
            loading={loading}
            error={error}
            onRetry={reload}
          />
        </div>

        <footer className="border-t border-border px-6 py-3">
          <Link
            to="/news"
            onClick={onClose}
            className="inline-flex items-center gap-1 rounded-lg text-sm text-text-secondary transition-colors hover:text-text-primary focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            See all
            <span aria-hidden>→</span>
          </Link>
        </footer>
      </div>
    </>
  )
}
