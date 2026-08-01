import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useLocation, type Location } from 'react-router'

import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'

/** Must match the .page-leave duration in index.css. */
const LEAVE_MS = 140

const LeavingContext = createContext(false)

/**
 * True while the route on screen is the OUTGOING one. The shell turns this into
 * the fade-out class; nothing else should need it.
 */
export function usePageLeaving(): boolean {
  return useContext(LeavingContext)
}

/**
 * Holds the outgoing route on screen for one short fade before the incoming one
 * mounts, so navigation reads as a handover rather than a cut.
 *
 * ⚠️ WHY THE ROUTES ARE RENDERED FROM A HELD LOCATION rather than from a second
 * copy of the outgoing page. React Router has no exit hook, so the usual trick is
 * to stash the rendered element and draw it alongside its replacement — but that
 * subtree keeps consuming the router's context, so a page matched on `:id` would
 * re-render for 140ms with no id and refetch against it. Passing a held location
 * to <Routes> is React Router's own supported answer: the outgoing page keeps the
 * location, the params and the match it was rendered with, right up to the swap.
 *
 * The cost is that the whole tree below — including the sidebar — is one frame
 * behind for those 140ms, so the active nav item lights up at the end of the fade
 * rather than the start. Its own colour transition covers that.
 *
 * ⚠️ Under reduced motion there is no hold at all. The route swaps on the same
 * tick it changed, because a 140ms stall with the fade switched off is not a
 * gentler transition — it is just latency.
 */
export function PageTransition({
  children,
}: {
  children: (location: Location) => ReactNode
}) {
  const location = useLocation()
  const reduced = usePrefersReducedMotion()
  const [displayed, setDisplayed] = useState(location)
  const [leaving, setLeaving] = useState(false)

  useEffect(() => {
    if (location.pathname === displayed.pathname) return

    if (reduced) {
      setDisplayed(location)
      return
    }

    setLeaving(true)
    const timer = setTimeout(() => {
      setDisplayed(location)
      setLeaving(false)
    }, LEAVE_MS)

    // A second navigation mid-fade restarts the clock against the newest
    // location rather than landing on the one we were already leaving.
    return () => clearTimeout(timer)
  }, [location, displayed, reduced])

  return (
    <LeavingContext.Provider value={leaving}>
      {children(displayed)}
    </LeavingContext.Provider>
  )
}
