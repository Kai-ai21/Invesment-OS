import GhostCursor from '@/components/GhostCursor'

/**
 * Ambient cursor light for the dashboard shell — NOT the landing page, which
 * keeps its own NeuralBackground field.
 *
 * Sits fixed and full-viewport at the lowest layer (zIndex 0), pointer-
 * transparent, with `screen` blend so it only ever adds light and never dims
 * the opaque content stacked above it — the sidebar and <main> are both z-10,
 * so every card, row and label paints over this.
 *
 * These are the effect's ORIGINAL VALUES, restored deliberately. The 20-point
 * trail and the fbm smoke that textures it are the character of the thing — it
 * is a comet, not a radial pool, and it is not meant to be symmetrical. Earlier
 * rounds cut brightness and collapsed the trail to one blob chasing legibility;
 * that bought contrast by deleting the effect, so it was reverted.
 *
 * ⚠️ WHAT THE LAYERING FIX DOES AND DOES NOT BUY YOU. The z-order is correct and
 * always was — but sitting BELOW the content is not the same as being hidden by
 * it, because most of this app's content has no background of its own. Walk up
 * from a filings "Summarise" pill and every ancestor — the button
 * (`.filing-action` is `background: transparent`), the row, the <li>, the <ul>,
 * the <section>, <main> — is rgba(0,0,0,0). The first opaque surface is the
 * SHELL ROOT, which paints BENEATH this layer. So on every bare list the glow
 * lands between the page colour and the text with nothing in between to conceal
 * it, and because it tracks the cursor it is always under whatever you are
 * reaching for. Only the cards (opaque #171a21) actually block it.
 *
 * So at these values the transparent controls on the filings and news lists DO
 * lose contrast under the cursor. That is a known, accepted trade for keeping
 * the effect. If it ever needs fixing, the lever is giving those rows a real
 * surface — NOT lowering brightness and not shortening the trail, both of which
 * were tried and just removed the effect.
 *
 * prefers-reduced-motion (render nothing, never start the loop), the hidden-tab
 * pause, and the fade-out on idle or on the pointer leaving the window all live
 * inside GhostCursor itself.
 */
export function DashboardBackground() {
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
