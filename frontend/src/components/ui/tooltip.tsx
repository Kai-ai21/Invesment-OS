import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Tooltip as TooltipPrimitive } from 'radix-ui'

import { cn } from '@/lib/utils'

/** ~400ms: long enough not to fire while the pointer is crossing the screen. */
const DELAY_MS = 400

/**
 * Wraps the app once. Keyboard focus opens WITHOUT this delay — Radix treats
 * focus as deliberate, which is the behaviour we want: a pointer sweeping past
 * an icon has not asked for anything, a Tab key press has.
 *
 * `skipDelayDuration` is what makes a row of icons feel like one control rather
 * than several: once a tooltip has been shown, moving to a neighbour within
 * 300ms opens instantly instead of restarting the wait.
 */
export function TooltipProvider({ children }: { children: ReactNode }) {
  return (
    <TooltipPrimitive.Provider delayDuration={DELAY_MS} skipDelayDuration={300}>
      {children}
    </TooltipPrimitive.Provider>
  )
}

/**
 * One tooltip. `children` is the trigger and is rendered AS the trigger via
 * asChild, so nothing extra lands in the DOM or the layout — important where the
 * trigger sits in a flex row or is itself a link.
 *
 * ⚠️ Content is described, never interactive. It is `aria-hidden` to Radix's own
 * accessible-description mechanism, so anything a screen reader needs must also
 * exist in the trigger's accessible name — every call site here either has a
 * visible label or an aria-label already.
 */
export function Tooltip({
  content,
  children,
  side = 'top',
  className,
}: {
  content: ReactNode
  children: ReactNode
  side?: 'top' | 'right' | 'bottom' | 'left'
  className?: string
}) {
  // Nothing to say — render the trigger bare rather than an empty bubble.
  if (!content) return <>{children}</>

  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          // Radix flips to the opposite side, then slides along it, to keep the
          // bubble on screen. The padding keeps it off the very edge of the
          // viewport rather than flush against it.
          collisionPadding={8}
          className={cn(
            'tooltip-in z-50 max-w-64 rounded-md border border-border bg-surface-raised px-2.5 py-1.5',
            'text-xs leading-snug text-text-secondary shadow-lg',
            // The bubble is measured against the viewport, so it must not be
            // able to grow past it on a narrow window.
            'origin-(--radix-tooltip-content-transform-origin)',
            className,
          )}
        >
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  )
}

/**
 * A figure inside a tooltip — a raw confidence score, a ticker, a price. Mono
 * and tabular for the same reason every other number in the app is: so a digit
 * is unambiguous and two of them line up.
 */
export function TooltipValue({ children }: { children: ReactNode }) {
  return (
    <span className="font-mono text-[11px] tabular-nums text-text-primary">
      {children}
    </span>
  )
}

/**
 * Text that may be clipped by `truncate`, with the full string on hover — but
 * ONLY when it is actually clipped.
 *
 * ⚠️ WHY IT MEASURES. Attaching a tooltip to everything that *could* overflow
 * means most of them repeat, word for word, text already fully visible on
 * screen. That trains the reader to ignore tooltips, which costs the ones that
 * carry something new. So the element is measured — scrollWidth past clientWidth
 * is the browser's own answer to "is this clipped" — and re-measured on resize,
 * because the sidebar collapsing changes every column's width.
 */
export function TruncatedText({
  text,
  className,
}: {
  text: string
  className?: string
}) {
  const [clipped, setClipped] = useState(false)
  const node = useRef<HTMLSpanElement | null>(null)

  const measure = useCallback((element: HTMLSpanElement | null) => {
    if (!element) return
    setClipped(element.scrollWidth > element.clientWidth)
  }, [])

  // A callback ref for the first measurement (the element exists, and its text
  // is laid out, by the time this runs) and an observer for every one after.
  const attach = useCallback(
    (element: HTMLSpanElement | null) => {
      node.current = element
      measure(element)
    },
    [measure],
  )

  useEffect(() => {
    const element = node.current
    if (!element) return
    const observer = new ResizeObserver(() => measure(element))
    observer.observe(element)
    return () => observer.disconnect()
  }, [measure, text])

  return (
    <Tooltip content={clipped ? text : null}>
      <span ref={attach} className={cn('block truncate', className)}>
        {text}
      </span>
    </Tooltip>
  )
}
