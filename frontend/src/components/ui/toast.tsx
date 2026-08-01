import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { Check, Info, TriangleAlert, X } from 'lucide-react'

import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { cn } from '@/lib/utils'

export type ToastVariant = 'success' | 'error' | 'info'

interface Toast {
  id: number
  variant: ToastVariant
  message: string
}

/** Long enough to read a short line twice; short enough not to linger. */
const DURATION_MS = 4000

/**
 * ⚠️ THREE, AND THE OLDEST GOES. A stack that grows without limit turns into a
 * wall the page has to be read around, and by the fourth message the first is no
 * longer news. Dropping from the top keeps the most recent — the one that
 * describes what just happened — always visible.
 */
const MAX_VISIBLE = 3

interface ToastApi {
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)

/**
 * The toast API.
 *
 * ⚠️ WHAT BELONGS HERE: "that worked" — saved, marked read, deleted, added. A
 * toast is unread by default and gone in four seconds, which makes it exactly
 * wrong for anything the reader has to act on or think about. Form validation
 * stays beside its field, a result the user is meant to sit with stays on the
 * page, and anything long enough to need re-reading stays where it can be
 * re-read.
 */
export function useToast(): ToastApi {
  const api = useContext(ToastContext)
  if (!api) throw new Error('useToast must be used within ToastProvider')
  return api
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const push = useCallback((variant: ToastVariant, message: string) => {
    setToasts((current) => {
      const id = (nextId.current += 1)
      // Trim from the FRONT, which is the top of the stack and the oldest.
      return [...current, { id, variant, message }].slice(-MAX_VISIBLE)
    })
  }, [])

  const api = useMemo<ToastApi>(
    () => ({
      success: (message) => push('success', message),
      error: (message) => push('error', message),
      info: (message) => push('info', message),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}

function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: Toast[]
  onDismiss: (id: number) => void
}) {
  return (
    // Not `hidden` when empty: an aria-live region has to be in the DOM BEFORE
    // the message lands in it, or assistive tech has nothing to observe and the
    // announcement is lost. It is pointer-transparent so an empty stack cannot
    // swallow clicks on whatever is underneath; each toast turns that back on.
    <div
      aria-live="polite"
      className="pointer-events-none fixed right-4 bottom-4 z-100 flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2"
    >
      {/* Rendered in arrival order inside a bottom-pinned column, so the newest
          is the one nearest the corner and the stack grows upward. */}
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  )
}

const VARIANT: Record<
  ToastVariant,
  { icon: typeof Check; colour: string; role: 'status' | 'alert'; label: string }
> = {
  // Existing status tokens, not new colours: a green here is the same green as a
  // supported claim everywhere else.
  success: {
    icon: Check,
    colour: 'var(--status-supported)',
    role: 'status',
    label: 'Success',
  },
  error: {
    icon: TriangleAlert,
    colour: 'var(--status-broken)',
    // role="alert" is assertive — it interrupts. Correct for a failure, and
    // wrong for the other two, which is why this is per-variant rather than one
    // role for the viewport.
    role: 'alert',
    label: 'Error',
  },
  info: {
    icon: Info,
    colour: 'var(--text-secondary)',
    role: 'status',
    label: 'Note',
  },
}

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: Toast
  onDismiss: (id: number) => void
}) {
  const reduced = usePrefersReducedMotion()
  const [paused, setPaused] = useState(false)
  const [leaving, setLeaving] = useState(false)

  const remaining = useRef(DURATION_MS)
  const startedAt = useRef(0)

  const close = useCallback(() => {
    if (reduced) {
      onDismiss(toast.id)
      return
    }
    // Let the fade run, then drop it. Under reduced motion there is no fade to
    // wait for, so waiting would just be 160ms of nothing happening.
    setLeaving(true)
    setTimeout(() => onDismiss(toast.id), 160)
  }, [onDismiss, reduced, toast.id])

  /**
   * ⚠️ THE TIMER BANKS ITS REMAINING TIME ON PAUSE. Restarting a fresh 4s on
   * every mouse-out would let a toast the reader keeps brushing past outlive
   * every other one; simply clearing without banking would make hovering
   * *shorten* nothing but also never resume. So: on pause, subtract what has
   * elapsed; on resume, run only the balance.
   */
  useEffect(() => {
    if (paused || leaving) return

    startedAt.current = Date.now()
    const timer = setTimeout(close, remaining.current)

    return () => {
      clearTimeout(timer)
      remaining.current -= Date.now() - startedAt.current
    }
  }, [paused, leaving, close])

  const { icon: Icon, colour, role, label } = VARIANT[toast.variant]

  return (
    <div
      role={role}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      // Focus as well as hover: reaching the close button by keyboard must not
      // race the timer that is about to remove the button being reached for.
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
      className={cn(
        // Same glass as the sidebar — a toast is chrome, not data.
        'glass-chrome pointer-events-auto flex items-start gap-2.5 rounded-lg border px-3.5 py-3 shadow-lg',
        leaving ? 'toast-out' : 'toast-in',
      )}
    >
      <Icon className="mt-px size-4 shrink-0" style={{ color: colour }} aria-hidden />
      {/* The variant is named for screen readers; sighted readers get the icon
          and the colour, and the message itself always says what happened. */}
      <span className="sr-only">{label}:</span>
      <p className="min-w-0 flex-1 text-sm leading-snug text-text-primary">
        {toast.message}
      </p>
      <button
        type="button"
        onClick={close}
        aria-label="Dismiss notification"
        className="-mt-0.5 -mr-1 shrink-0 rounded p-1 text-text-muted transition-colors hover:text-text-primary focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <X className="size-3.5" aria-hidden />
      </button>
    </div>
  )
}
