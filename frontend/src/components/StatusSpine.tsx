import { statusColor } from '@/components/StatusBadge'
import { cn } from '@/lib/utils'

/** Width of the spine, shared so table cells can reserve the same gutter. */
export const SPINE_WIDTH = '3px'

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
