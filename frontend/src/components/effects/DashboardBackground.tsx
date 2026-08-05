import GhostCursor from '@/components/GhostCursor'
import { useCoarsePointer } from '@/hooks/useMediaQuery'

/**
 * Ambient light for the dashboard shell — NOT the landing page, which keeps its own
 * NeuralBackground field.
 *
 * TWO IMPLEMENTATIONS OF ONE IDEA, chosen by input device. A cursor-tracking WebGL
 * comet where there is a cursor to track, and a static CSS wash where there is not.
 * The dashboard is never a flat dark rectangle either way.
 *
 * ⚠️ ON A TOUCH DEVICE GhostCursor IS NOT RENDERED AT ALL, and "not rendered" is the
 * requirement — not hidden, not transparent, not paused. This is the fix for a bug
 * where the whole dashboard went black on phones while the landing page was fine:
 *
 *   GhostCursor builds `new THREE.WebGLRenderer()` inside a useEffect, unguarded.
 *   When a browser cannot hand out a WebGL context — mobile Safari under memory
 *   pressure, Low Power Mode, Lockdown Mode, or simply too many tabs — three.js
 *   THROWS "Error creating WebGL context". The throw escapes the effect, and with no
 *   error boundary anywhere in this app React unmounts the entire root. What is left
 *   on screen is <body>, whose background is --background (#0f1115). A black page.
 *
 *   The landing page survived the same conditions because NeuralBackground is
 *   Canvas 2D, which never fails this way. That asymmetry is the whole bug report.
 *
 * ⚠️ DETECTED WITH `(pointer: coarse)`, NEVER A WIDTH BREAKPOINT. A narrow laptop
 * window has a cursor and keeps the comet; a large tablet has no cursor and must not
 * get it however much room it has. See useCoarsePointer.
 *
 * GhostCursor is additionally guarded internally now, so a WebGL failure on a device
 * that DOES have a cursor degrades to no effect rather than to no application. This
 * component and that guard are independent fixes for the same fault: one removes the
 * common cause, the other removes the consequence.
 */
export function DashboardBackground() {
  const coarsePointer = useCoarsePointer()

  // Static, cool, and slightly richer than the shared .ambient-backdrop that sits
  // above it — with no comet moving underneath, this layer is carrying the shell's
  // character on its own. Three soft radial blobs fixed to the viewport: no canvas,
  // no context, no animation frame, nothing to fail.
  if (coarsePointer) {
    return (
      <div
        aria-hidden
        className="ambient-backdrop-static pointer-events-none fixed inset-0 z-0"
      />
    )
  }

  return (
    <GhostCursor
      color="#ffffff"
      brightness={1.6}
      bloomStrength={0.3}
      bloomRadius={2.5}
      trailLength={20}
      grainIntensity={0.04}
      zIndex={0}
      // The vendored CSS positions the layer `absolute`; override to a fixed,
      // full-viewport layer pinned to the shell.
      style={{ position: 'fixed', inset: 0 }}
    />
  )
}

/*
 * WHAT THE ORIGINAL NOTES ON THIS FILE SAID, kept because the values above are
 * deliberate and were re-litigated once already:
 *
 * These are the effect's ORIGINAL VALUES, restored deliberately. The 20-point trail
 * and the fbm smoke that textures it are the character of the thing — it is a comet,
 * not a radial pool, and it is not meant to be symmetrical. Earlier rounds cut
 * brightness and collapsed the trail to one blob chasing legibility; that bought
 * contrast by deleting the effect, so it was reverted.
 *
 * Sitting BELOW the content is not the same as being hidden by it, because most of
 * this app's content has no background of its own. Walk up from a filings
 * "Summarise" pill and every ancestor is rgba(0,0,0,0); the first opaque surface is
 * the shell root, which paints BENEATH this layer. So on every bare list the glow
 * lands between the page colour and the text. Only the cards (opaque #171a21) block
 * it. That contrast loss under the cursor is a known, accepted trade. If it ever
 * needs fixing, the lever is giving those rows a real surface — NOT lowering
 * brightness and not shortening the trail, both of which were tried and just removed
 * the effect.
 *
 * prefers-reduced-motion (render nothing, never start the loop), the hidden-tab
 * pause, and the fade-out on idle or on the pointer leaving the window all live
 * inside GhostCursor itself.
 */
