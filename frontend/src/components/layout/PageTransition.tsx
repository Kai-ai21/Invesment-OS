import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
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

  // ⚠️ THE EFFECT IS KEYED ON THE PATH, NOT THE LOCATION OBJECT, AND THAT IS WHAT
  // STOPS THE FADE FROM BEING STARVED. Its cleanup clears the pending timer, so
  // every re-run cancels the swap that was already in flight and starts a new
  // 140ms wait. Re-run it faster than every 140ms and `displayed` NEVER advances.
  //
  // That is not hypothetical: a signed-out click into the app produced hundreds of
  // redirects to the same path in a burst, each one a NEW location object with a
  // new key. The object identity changed every time while the path never did, so
  // the clock reset continuously, `displayed` stayed on the route being left, and
  // the user watched <Navigate> render null — a blank page — until the burst
  // finished. The redirect storm is fixed at its source in RequireAuth; this makes
  // the transition robust to any future burst rather than trusting that none
  // happens again.
  //
  // The location is read through a ref so the swap still lands on the CURRENT one,
  // complete with its search and hash, without those being effect dependencies.
  const latest = useRef(location)
  latest.current = location

  const target = location.pathname
  const shown = displayed.pathname

  useEffect(() => {
    if (target === shown) return

    if (reduced) {
      setDisplayed(latest.current)
      return
    }

    setLeaving(true)
    const timer = setTimeout(() => {
      setDisplayed(latest.current)
      setLeaving(false)
    }, LEAVE_MS)

    // A navigation to a DIFFERENT path mid-fade restarts the clock against the
    // newest one rather than landing on the one we were already leaving. A repeat
    // of the same path no longer re-runs this effect at all.
    return () => clearTimeout(timer)
  }, [target, shown, reduced])

  return (
    <LeavingContext.Provider value={leaving}>
      {children(displayed)}
    </LeavingContext.Provider>
  )
}
