import { CursorSpotlight } from '@/components/effects/CursorSpotlight'
import { useCoarsePointer } from '@/hooks/useMediaQuery'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'

/**
 * Ambient light for the dashboard shell — NOT the landing page, which keeps its own
 * NeuralBackground field.
 *
 * TWO IMPLEMENTATIONS OF ONE IDEA, chosen by input device. A cursor-tracking
 * spotlight where there is a cursor to track, and a static CSS wash where there is
 * not. The dashboard is never a flat dark rectangle either way.
 *
 * ⚠️ DETECTED WITH `(pointer: coarse)`, NEVER A WIDTH BREAKPOINT. A narrow laptop
 * window has a cursor and keeps the spotlight; a large tablet has no cursor and must
 * not get it however much room it has. See useCoarsePointer.
 *
 * ⚠️ REDUCED MOTION TAKES THE SAME BRANCH AS TOUCH, and that is the point of routing
 * it here rather than switching the animation off inside the effect. "No motion"
 * should not mean "no ambient light" — it means the light stops following the
 * pointer. The static wash is exactly that: the same visual family, holding still.
 *
 * HISTORY, because the shape of this file is a response to a real fault. The
 * cursor-side effect used to be a vendored WebGL component (GhostCursor, built on
 * `three`). It constructed a `THREE.WebGLRenderer` inside an effect; on a browser
 * that would not grant a context — mobile Safari under memory pressure, Low Power
 * Mode, Lockdown Mode — three.js threw, the throw escaped the effect, and React
 * unmounted the entire root. The dashboard went black on phones while the landing
 * page, which is Canvas 2D, was fine. The coarse-pointer branch below was the fix
 * for the common cause and ErrorBoundary for the consequence.
 *
 * The replacement removes the cause outright: a radial gradient on one element has
 * no context to be denied, nothing to initialise and nothing to throw. The branch
 * stays regardless — a phone still has no cursor to follow, so the effect would be
 * meaningless there even if it were free.
 */
export function DashboardBackground() {
  const coarsePointer = useCoarsePointer()
  const reducedMotion = usePrefersReducedMotion()

  // Static, cool, and slightly richer than the shared .ambient-backdrop that sits
  // above it — with no spotlight moving underneath, this layer is carrying the
  // shell's character on its own. Three soft radial blobs fixed to the viewport.
  if (coarsePointer || reducedMotion) {
    return (
      <div
        aria-hidden
        className="ambient-backdrop-static pointer-events-none fixed inset-0 z-0"
      />
    )
  }

  return <CursorSpotlight />
}

/*
 * ON SITTING BELOW THE CONTENT, which is not the same as being hidden by it.
 *
 * Most of this app's content has no background of its own: walk up from a filings
 * "Summarise" pill and every ancestor is rgba(0,0,0,0), so the first opaque surface
 * is the shell root, which paints BENEATH this layer. On every bare list the light
 * therefore lands between the page colour and the text rather than behind it. Only
 * the real surfaces — cards at #171a21, bg-surface-raised at #1d212b — block it.
 *
 * Under the old WebGL comet that cost measurable contrast, and the note here used to
 * record it as an accepted trade. It is no longer accepted, and no longer a trade:
 * the spotlight's centre is 3.5% white, which lifts the page about eight values per
 * channel. Text contrast moves in the third decimal place. If a future revision
 * wants more light, the lever is still giving those rows a real surface — NOT
 * raising the alpha here, which is the change that made the old one unreadable.
 *
 * ResearchPage's "Held" pill cites this note for exactly that reason: it uses a
 * solid bg-surface-raised rather than a translucent fill so the layer cannot show
 * through it.
 */
