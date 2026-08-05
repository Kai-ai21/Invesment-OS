import { useEffect, useState } from 'react'

/**
 * A live `matchMedia` result, subscribed rather than read once.
 *
 * Generalised from usePrefersReducedMotion, which predates it and keeps its own
 * copy on purpose — it is the one JS-side read of the motion preference and reads
 * better named after what it answers. Everything else that needs a media query
 * from JavaScript should come through here.
 *
 * Subscribing matters more than it looks: a tablet can gain a trackpad, a window
 * can be dragged between a laptop screen and an external monitor, and rotating a
 * phone changes the width query mid-session. All three would otherwise be stuck on
 * whatever was true at mount.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)

  useEffect(() => {
    const list = window.matchMedia(query)
    const sync = () => setMatches(list.matches)
    // Re-read on mount: the answer can change between the initial state above and
    // this effect running.
    sync()
    list.addEventListener('change', sync)
    return () => list.removeEventListener('change', sync)
  }, [query])

  return matches
}

/**
 * Whether the primary pointer is COARSE — a finger or a stylus rather than a mouse.
 *
 * ⚠️ THIS IS NOT "IS THE SCREEN SMALL", AND THE TWO MUST NOT BE CONFLATED. A laptop
 * window dragged narrow still has a cursor and should keep the cursor-tracking
 * effects; a 12" tablet has a huge screen and no cursor at all. Anything that exists
 * because of the INPUT DEVICE asks this; anything that exists because of AVAILABLE
 * ROOM asks a width query instead. In this app the ambient background asks this one
 * and the sidebar layout asks a width one, and that split is deliberate.
 */
export function useCoarsePointer(): boolean {
  return useMediaQuery('(pointer: coarse)')
}

/**
 * Whether the viewport is too narrow to give a permanent sidebar away for free.
 *
 * 1024px is Tailwind's `lg`, chosen so the breakpoint matches the one the utility
 * classes elsewhere in the shell use rather than introducing a second, private
 * idea of "narrow" a few pixels away from it.
 */
export function useNarrowViewport(): boolean {
  return useMediaQuery('(max-width: 1023px)')
}
