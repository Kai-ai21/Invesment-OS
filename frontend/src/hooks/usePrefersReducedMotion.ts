import { useEffect, useState } from 'react'

const QUERY = '(prefers-reduced-motion: reduce)'

/**
 * THE ONE JS-SIDE READ OF THE MOTION PREFERENCE. Anything animated in CSS is
 * disabled by a `@media (prefers-reduced-motion: reduce)` block instead — this
 * hook exists only for the motion we drive from JavaScript (the number roll-up,
 * and the delay the page transition holds the outgoing route for), where there is
 * no stylesheet to switch off.
 *
 * Subscribed rather than read once, so toggling the OS setting takes effect
 * without a reload.
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => window.matchMedia(QUERY).matches)

  useEffect(() => {
    const query = window.matchMedia(QUERY)
    const sync = () => setReduced(query.matches)
    // Re-read on mount too: the preference can change between the initial state
    // above and this effect.
    sync()
    query.addEventListener('change', sync)
    return () => query.removeEventListener('change', sync)
  }, [])

  return reduced
}
