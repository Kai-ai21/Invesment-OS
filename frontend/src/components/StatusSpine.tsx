import { statusColor } from '@/components/StatusBadge'
import { cn } from '@/lib/utils'

/** Width of the spine, shared so table cells can reserve the same gutter. */
export const SPINE_WIDTH = '3px'

/**
 * THE INSET SURFACE — the shell every status-bearing surface shares.
 *
 * A well cut into the page rather than a panel resting on it: the face is
 * DARKER than #0f1115, and it is framed by a DOUBLE border — the hairline on the
 * element's own edge, then a fainter ring held 2px outside it with a band of
 * page colour showing between the two.
 *
 * ⚠️ THE OUTER RING IS AN `outline`, NOT A BORDER OR A RING UTILITY, and the
 * reason is corners. `outline` follows `border-radius` in every browser this
 * ships to, and `outline-offset` pushes it outward WITHOUT taking layout space,
 * so a list's rhythm is set by its gap alone. A box-shadow spread would work
 * too, but it would have to paint the 2px band in the page colour, which breaks
 * the moment one of these sits on anything but --background.
 *
 * ⚠️ THE RING NEEDS ROOM. It occupies 3px outside the border box on every side,
 * so any list of these must keep a gap of at least 12px or adjacent rings close
 * to within a few pixels and the pair reads as one smudged edge. Every call site
 * is on gap-4 (16px), which leaves 10px of clear page between rings.
 *
 * `ring-0` is not decoration: <Card> ships a `ring-1 ring-foreground/10`, which
 * would sit in the 2px band and fill the very gap the effect is made of.
 *
 * No background and no hover — the call site adds both, because they are the two
 * things that legitimately differ between these surfaces (see INSET_CARD, and
 * the read/unread note in AlertsPage).
 */
export const INSET_SURFACE =
  'rounded-xl border border-border ring-0 outline-1 outline-offset-2 outline-card-ring'

/**
 * INSET_SURFACE plus the hover state, for the ones you can click.
 *
 * Both edges brighten and the inner one brightens further, so the two never
 * converge into a single thick frame. The spine is untouched — it carries
 * meaning, not interaction state.
 */
export const INSET_CARD = `${INSET_SURFACE} transition-colors hover:border-border-strong hover:outline-card-ring-strong`

/**
 * The 3px status-coloured stripe down the left edge of a status-bearing card.
 *
 * ⚠️ THE COLOUR IS DELIBERATELY CONFINED TO THIS STRIPE. The card keeps a plain
 * hairline border and an untinted background: a list where every card is fully
 * outlined in red or amber reads as an emergency, and the app's colour discipline
 * depends on status colours staying rare enough to mean something. The spine is
 * the smallest mark that still lets someone scan a column and see where the
 * trouble is.
 *
 * HOW IT FOLLOWS THE ROUNDED CORNERS. It is a plain rectangle pinned to the left
 * edge; the CARD clips it. Every surface this is used on already has
 * `overflow-hidden` with the card's own radius, so the stripe is cut to the curve
 * for free. Drawing a rounded stripe instead would leave a hairline gap between
 * the stripe's curve and the card's, which is exactly the artefact that makes
 * this treatment look cheap.
 *
 * Renders NOTHING when there is no status — a portfolio row for something the
 * user never wrote a thesis about gets the hairline and no stripe, because there
 * is no status to report rather than a neutral one.
 */
export function StatusSpine({
  status,
  className,
}: {
  /** Null or undefined renders nothing at all. */
  status: string | null | undefined
  className?: string
}) {
  if (!status) return null

  return (
    <span
      aria-hidden
      className={cn('pointer-events-none absolute inset-y-0 left-0', className)}
      style={{ width: SPINE_WIDTH, background: statusColor(status) }}
    />
  )
}

/**
 * The same spine as a LEFT BORDER, for table rows.
 *
 * A <tr> is not a reliable positioning context — an absolutely positioned child
 * resolves against the table or the page rather than the row, so the component
 * above cannot be used there. A border on the row's first cell draws the same
 * 3px stripe with the same colour from the same map.
 *
 * A row with no status still gets the border, TRANSPARENT: reserving the gutter
 * keeps every row's content on the same left edge, so a portfolio with a mix of
 * tracked and untracked holdings does not look ragged.
 */
export function spineBorderStyle(status: string | null | undefined) {
  return {
    borderLeftWidth: SPINE_WIDTH,
    borderLeftStyle: 'solid' as const,
    borderLeftColor: status ? statusColor(status) : 'transparent',
  }
}
