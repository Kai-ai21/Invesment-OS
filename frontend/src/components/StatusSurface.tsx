import { statusColor } from '@/components/StatusBadge'
import { cn } from '@/lib/utils'

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
 * converge into a single thick frame. The glow is untouched by this — it has its
 * own hover, on its own timing.
 */
export const INSET_CARD = `${INSET_SURFACE} transition-colors hover:border-border-strong hover:outline-card-ring-strong`

/**
 * ⚠️ WHAT EVERY HOST OF A <StatusGlow> MUST CARRY. The glow is `-z-10`, which
 * places it above its parent's own background and below the parent's in-flow
 * content — but ONLY inside a stacking context. Without `isolate` the negative
 * layer escapes to the nearest ancestor context and paints BEHIND the card's
 * fill, i.e. nowhere. `relative` is the positioning context it pins to, and
 * `group/glow` is what its hover reads.
 *
 * Kept as one constant rather than three classes at four call sites because
 * dropping any one of them fails silently: `isolate` alone makes the glow
 * invisible, `group/glow` alone makes it inert on hover, and neither looks like
 * a bug so much as like the effect was never added.
 *
 * The holdings table is the one place these three are split apart — a table row
 * cannot position the glow and a table cell should not scope its hover. See the
 * note on the leading <td> there.
 */
export const GLOW_HOST = 'group/glow relative isolate'

/**
 * How far the bloom reaches from the corner. The gradient is given this as an
 * EXPLICIT radius rather than a keyword: from a corner, `closest-side` measures
 * zero (two of the four sides pass through the origin) and `farthest-corner`
 * would scale with the card's height, so a tall reflection card would bloom
 * twice as far as a short alert.
 */
const GLOW_RADIUS = '38px'

/**
 * A soft radial bloom of the status colour, out of the card's TOP-LEFT corner.
 *
 * ⚠️ THIS REPLACED A 3px COLOURED LEFT BORDER, and the reason is worth keeping:
 * the spine was a generic device — every list on the web has one — and it said
 * exactly what the status badge two inches to its right already said in words.
 * A bloom out of the corner is the same signal (scan a column, see where the
 * trouble is) without a second hard edge competing with the hairline and the
 * outer ring the card already carries.
 *
 * ⚠️ PENDING RENDERS NOTHING, deliberately, and so does a null status. "Pending"
 * means no evidence has been gathered yet — there is no finding to point at, and
 * lighting a corner to announce an absence is how a quiet list becomes a noisy
 * one. Nothing is lost: the badge still spells PENDING out. The practical effect
 * is that a page of untouched theses is completely calm and the one card that
 * has actually moved is the only thing glowing on it.
 *
 * ⚠️ THE OPACITY IS SPLIT BETWEEN THE GRADIENT AND THE ELEMENT, on purpose. The
 * gradient is mixed at its BRIGHT value (35%) and the element rests at 0.85 of
 * it, so hover is one `opacity` transition — the one property that animates
 * cheaply and never repaints the gradient. Interpolating between two
 * `radial-gradient` images would be the obvious alternative and is both slower
 * and inconsistently supported. Rest lands at ~30% and hover at 35%.
 *
 * Clipping is the card's, not this element's: every host already has
 * `overflow-hidden` with the card radius, so the quarter-disc is cut to the
 * curve for free. Same trick the spine used to follow the rounded corner.
 */
export function StatusGlow({
  status,
  className,
}: {
  /** Null, undefined or 'pending' renders nothing at all. */
  status: string | null | undefined
  className?: string
}) {
  if (!status || status === 'pending') return null

  const color = statusColor(status)

  return (
    <span
      aria-hidden
      className={cn(
        'pointer-events-none absolute top-0 left-0 -z-10 opacity-[0.85] transition-opacity duration-200 group-hover/glow:opacity-100',
        className,
      )}
      style={{
        width: GLOW_RADIUS,
        height: GLOW_RADIUS,
        // Transparent by 70% of the radius, so the bloom has faded out well
        // inside its own box and never ends on a visible edge.
        background: `radial-gradient(circle ${GLOW_RADIUS} at 0 0, color-mix(in srgb, ${color} 35%, transparent) 0%, transparent 70%)`,
      }}
    />
  )
}
