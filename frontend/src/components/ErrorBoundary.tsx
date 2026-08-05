import { Component, type ErrorInfo, type ReactNode } from 'react'
import { RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'

/**
 * The last line of defence: catches a render-time crash and shows a page instead of
 * nothing.
 *
 * ⚠️ WHY THIS EXISTS, CONCRETELY. React's response to an uncaught error anywhere in
 * the tree is to unmount THE ENTIRE ROOT — not the component that threw, not its
 * branch, all of it. With no boundary the user is left looking at <body>, whose
 * background is --background (#0f1115), so the failure mode of any single component
 * is a completely black page with no message, no controls and nothing in the UI
 * suggesting a reload would help.
 *
 * That is not hypothetical here. GhostCursor built a WebGL context in an effect
 * without guarding it; on a browser that would not grant one, three.js threw, and the
 * whole dashboard went black on phones while the landing page — which uses Canvas 2D
 * — was fine. That specific throw is now handled at its source, but "a component
 * threw" is a permanent category of bug and blanking the application is never the
 * right answer to it.
 *
 * ⚠️ WHAT A BOUNDARY DOES NOT CATCH, because the gaps matter when you are debugging
 * one: errors inside event handlers, anything thrown asynchronously (setTimeout, a
 * promise rejection, an await after the first suspension point), and errors thrown by
 * the boundary's own render. It DOES catch render, constructor and lifecycle errors —
 * including useEffect bodies, which run during commit and are covered. The GhostCursor
 * case above was an effect, which is exactly why a boundary answers it.
 *
 * A CLASS, and there is no choice about that: `getDerivedStateFromError` and
 * `componentDidCatch` have no hook equivalents. This is the one class component in
 * the app and it is not a style inconsistency to be tidied away.
 */
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // The component stack is the whole value of logging here — the error alone tells
    // you what broke, and this tells you where it was mounted, which is usually the
    // faster half of the answer. Deliberately console only: there is no reporting
    // service in this app and adding one is a separate decision.
    console.error('Crash caught by ErrorBoundary:', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      // Centred on its own full-height surface rather than inside the shell — the
      // shell is above this boundary and may itself be what failed, so the fallback
      // cannot assume any of the app's chrome is on screen.
      <div
        role="alert"
        className="flex h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center"
      >
        <div>
          <p className="font-heading text-base font-medium text-text-primary">
            Something broke on this screen
          </p>
          {/* No error message, no stack. It would be a variable name or a minified
              frame — nothing the reader can act on, and it reads as the app leaking
              its insides. The console has the real thing, which is where anyone able
              to use it will look. */}
          <p className="mt-1 text-sm text-text-secondary">
            The rest of the app is fine. Reloading usually clears it.
          </p>
        </div>

        {/* A FULL RELOAD, not a state reset. Clearing `error` would re-render the
            same tree from the same state that just crashed, so the overwhelmingly
            likely result is an immediate second crash — a button that visibly does
            nothing. A reload rebuilds from scratch, which is the thing that actually
            tends to work. */}
        <Button variant="outline" onClick={() => window.location.reload()}>
          <RefreshCw aria-hidden />
          Reload
        </Button>
      </div>
    )
  }
}
