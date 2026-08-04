import type { ReactNode } from 'react'
import { Link } from 'react-router'

/**
 * The frame both /login and /signup sit in. Extracted so the two cannot drift —
 * they are the same screen with a different form in the middle, and a user moving
 * between them by the footer link should see nothing move but the fields.
 *
 * Deliberately OUTSIDE AppShell: there is no sidebar, no nav and no ambient
 * dashboard backdrop here, because none of those belong to someone who is not
 * signed in — and half of them would fire authenticated requests that 401.
 */
export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string
  subtitle: string
  children: ReactNode
  footer: ReactNode
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6 py-12">
      <div className="w-full max-w-sm">
        {/* The wordmark, matching the sidebar's — the same app, before you are in
            it. Links home rather than being inert: the landing page is public, and
            a logo that does nothing reads as broken. */}
        <Link
          to="/"
          className="mb-8 flex items-center justify-center gap-2.5 rounded-lg focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <span
            aria-hidden
            className="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-raised text-xs font-medium text-text-primary"
          >
            KO
          </span>
          <span className="font-display text-sm tracking-[0.01em] text-text-primary">
            Kailaas OS
          </span>
        </Link>

        <div className="rounded-xl border border-border bg-surface-inset p-6 outline-1 outline-offset-2 outline-card-ring">
          <h1 className="font-heading text-xl font-medium text-text-primary">{title}</h1>
          <p className="mt-1 mb-6 text-sm text-text-secondary">{subtitle}</p>
          {children}
        </div>

        <p className="mt-6 text-center text-sm text-text-secondary">{footer}</p>
      </div>
    </div>
  )
}

/**
 * ⚠️ INLINE, NOT A TOAST, and that is a deliberate difference from the rest of the
 * app. A toast is for something that happened elsewhere and is now over; a rejected
 * login is about the form still on screen and still needing attention. It also
 * disappears on a timer, which is exactly wrong for a message someone has to act on.
 *
 * role="alert" so it is announced the moment it appears — a sighted user sees the
 * form fail to go anywhere, and this is the equivalent signal.
 */
export function FormError({ children }: { children: ReactNode }) {
  return (
    <p
      role="alert"
      className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-status-broken"
    >
      {children}
    </p>
  )
}

/** A labelled field. The label is a real <label>, so clicking it focuses the input
 *  and a screen reader announces the two together. */
export function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm text-text-secondary">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-text-muted">{hint}</p>}
    </div>
  )
}
