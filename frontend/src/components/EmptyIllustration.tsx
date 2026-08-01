import { cn } from '@/lib/utils'

/**
 * Which absence this is. Named for the SUBJECT, not the feeling — there is no
 * "sad" or "celebration" variant here, and there should not be.
 */
export type EmptyVariant =
  | 'theses'
  | 'alerts'
  | 'holdings'
  | 'reflections'
  | 'news'
  | 'patterns'

/**
 * A small geometric mark for an empty state.
 *
 * ⚠️ A MARK, NOT A PICTURE. No characters, no scenes, no metaphors about empty
 * boxes or lost explorers — this app tells someone their investment thesis is
 * breaking, and a cartoon in that context reads as either flippant or padding.
 * Each variant is a few strokes abstracted from the thing that is missing: the
 * rows of a list, the line of a price, the marks of a written note.
 *
 * ⚠️ AND IT IS SMALL. 56px, above copy that is doing the actual work. The copy
 * is the message — "Silence means nothing meaningful has changed" says something
 * a graphic cannot — and this sits above it as punctuation, never in place of it.
 *
 * Monochrome throughout, on `currentColor` inherited from the muted text around
 * it, so it can never compete with a status colour for attention.
 */
export function EmptyIllustration({
  variant,
  className,
}: {
  variant: EmptyVariant
  className?: string
}) {
  return (
    <svg
      viewBox="0 0 56 56"
      width={56}
      height={56}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.25}
      strokeLinecap="round"
      strokeLinejoin="round"
      // Decorative: every one of these sits directly above copy that says the
      // same thing in words, so announcing it would only repeat that copy.
      aria-hidden
      focusable="false"
      className={cn('text-text-muted/50', className)}
    >
      {SHAPES[variant]}
    </svg>
  )
}

/**
 * One entry per variant, drawn on a 56×56 grid with an 8px margin.
 *
 * The dashed element in each is the ABSENT one — the row that has not been
 * written, the alert that has not fired — which is what makes these read as
 * "nothing here yet" rather than as decoration.
 */
const SHAPES: Record<EmptyVariant, React.ReactNode> = {
  // Stacked rows: a list of theses, the last one not yet written.
  theses: (
    <>
      <rect x="8" y="12" width="40" height="9" rx="2.5" />
      <rect x="8" y="25.5" width="40" height="9" rx="2.5" opacity={0.6} />
      <rect x="8" y="39" width="40" height="9" rx="2.5" strokeDasharray="3 3" opacity={0.4} />
    </>
  ),

  // A bell outline, silent — no ring arcs. The copy carries "silence means
  // nothing meaningful has changed"; this is just its shape.
  alerts: (
    <>
      <path d="M18 34a10 10 0 0 1 20 0v4l2.5 4h-25l2.5-4Z" />
      <path d="M24.5 42a3.5 3.5 0 0 0 7 0" opacity={0.6} />
      <path d="M28 20v4" opacity={0.6} />
    </>
  ),

  // A price line over a baseline, the last leg not yet drawn.
  holdings: (
    <>
      <path d="M8 44h40" opacity={0.45} />
      <path d="M10 36l8-7 7 5 8-11" />
      <path d="M33 23l6 8 7-4" strokeDasharray="3 3" opacity={0.45} />
    </>
  ),

  // Ruled lines on a page: a note not yet written.
  reflections: (
    <>
      <rect x="12" y="9" width="32" height="38" rx="3" opacity={0.7} />
      <path d="M19 20h18" />
      <path d="M19 27h18" opacity={0.7} />
      <path d="M19 34h11" strokeDasharray="3 3" opacity={0.45} />
    </>
  ),

  // Headline over two lines of body — a story with nothing under it.
  news: (
    <>
      <rect x="9" y="13" width="38" height="30" rx="3" opacity={0.7} />
      <path d="M15 21h14" />
      <path d="M15 28h26" opacity={0.6} />
      <path d="M15 35h20" strokeDasharray="3 3" opacity={0.4} />
    </>
  ),

  // Three points with a line found through two of them: a pattern needs more
  // than a pair before it is one, which is exactly what the copy says.
  patterns: (
    <>
      <circle cx="15" cy="38" r="3.5" />
      <circle cx="28" cy="22" r="3.5" opacity={0.7} />
      <circle cx="41" cy="31" r="3.5" strokeDasharray="3 3" opacity={0.45} />
      <path d="M17.6 35.7 25.4 24.3" opacity={0.5} />
      <path d="M30.6 24.4 38.4 28.6" strokeDasharray="3 3" opacity={0.35} />
    </>
  ),
}
