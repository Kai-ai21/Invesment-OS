import { useEffect, useRef } from 'react'

/**
 * A soft light that follows the cursor, one element and no canvas.
 *
 * Replaces the vendored WebGL GhostCursor, which cost a `three` dependency, a
 * WebGL context and a render loop to do a job a single radial gradient does. It
 * also washed content out: the old note on DashboardBackground recorded that as a
 * known, accepted trade. It is not accepted here — see the numbers below.
 *
 * ⚠️ NOT A GLOW. A glow has a bright core and bleeds colour; this is a REVEAL —
 * the page is a fraction lighter where the pointer is, as though a lamp were
 * somewhere off to the side. Pure white at a few percent over #0f1115 lands around
 * #191b1f, which is a tone of the same grey rather than a second colour in the
 * palette. No bloom, no saturation, nothing that looks emitted.
 *
 * ⚠️ IT NEVER RE-RENDERS REACT. A pointermove handler that called setState would
 * re-run this component — and every child of whatever renders it — at pointer
 * frequency, which on a 120Hz trackpad is 120 renders a second to move a
 * background. The coordinates go straight onto the DOM node as custom properties,
 * and even the fade in/out is a data attribute set imperatively, so the React tree
 * is untouched from mount to unmount.
 */
export function CursorSpotlight() {
  const ref = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const node = ref.current
    if (!node) return

    // The most recent pointer position, and whether a frame is already booked.
    // Kept in closure rather than state for the reason in the docblock.
    let x = 0
    let y = 0
    let frame = 0

    // ⚠️ THE WRITE HAPPENS ONCE PER ANIMATION FRAME, NOT ONCE PER EVENT. A mouse
    // can emit several moves between two frames and a trackpad emits many; each
    // one would otherwise dirty the same style the browser is about to read back.
    // Coalescing to rAF means at most one write per painted frame, and the write
    // lands at the moment the browser is ready to use it.
    const paint = () => {
      frame = 0
      node.style.setProperty('--spotlight-x', `${x}px`)
      node.style.setProperty('--spotlight-y', `${y}px`)
    }

    const onMove = (event: PointerEvent) => {
      x = event.clientX
      y = event.clientY
      // Marked active on the first move rather than at mount: until the pointer
      // has actually moved we do not know where it is, and a spotlight sitting at
      // 0,0 on load would be a bright corner nobody asked for.
      node.dataset.active = 'true'
      if (!frame) frame = requestAnimationFrame(paint)
    }

    // Leaving the window, and switching away from it, are the same thing as far as
    // this is concerned: there is no cursor over the page, so there is nothing to
    // light. The fade itself is a CSS transition on opacity.
    const onLeave = () => {
      node.dataset.active = 'false'
    }

    window.addEventListener('pointermove', onMove, { passive: true })
    document.documentElement.addEventListener('pointerleave', onLeave)
    window.addEventListener('blur', onLeave)

    return () => {
      // ⚠️ CANCEL THE BOOKED FRAME. Without this, a pending callback can fire after
      // unmount and write to a detached node — harmless today, but it is also the
      // shape of a leak if this ever holds anything heavier than two numbers.
      if (frame) cancelAnimationFrame(frame)
      window.removeEventListener('pointermove', onMove)
      document.documentElement.removeEventListener('pointerleave', onLeave)
      window.removeEventListener('blur', onLeave)
    }
  }, [])

  return <div ref={ref} aria-hidden className="cursor-spotlight" data-active="false" />
}
