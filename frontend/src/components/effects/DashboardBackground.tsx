import GhostCursor from '@/components/GhostCursor'

/**
 * Ambient cursor light for the dashboard shell — NOT the landing page, which
 * keeps its own NeuralBackground field.
 *
 * Sits fixed and full-viewport at the lowest layer (zIndex 0), pointer-
 * transparent, with `screen` blend so it only ever adds light and never dims
 * the opaque content stacked above it. Bright white glow that follows the
 * cursor; because GhostCursor fades out when the pointer is still, it settles
 * back to just the static ambient blobs at rest.
 *
 * prefers-reduced-motion (render nothing, never start the loop) and the
 * hidden-tab pause both live inside GhostCursor itself.
 */
export function DashboardBackground() {
  return (
    <GhostCursor
      color="#ffffff"
      brightness={1.0}
      bloomStrength={0.2}
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
