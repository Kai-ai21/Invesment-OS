import { cn } from '@/lib/utils'

/**
 * The Kailaas ridgeline: one irregular polyline that reads as a mountain ridge and
 * as a price chart at the same time, with a short dotted tail falling away after
 * the summit. The summit sits at 71% of the width — late, so the long jagged
 * approach is the bulk of the mark and the descent is a coda.
 *
 * ⚠️ INLINED RATHER THAN <img src="/logo.svg">, AND THAT IS THE WHOLE REASON THIS
 * COMPONENT EXISTS. `currentColor` resolves against the element's inherited `color`,
 * and an SVG loaded through <img> is a separate document with no access to this
 * page's cascade — it would paint black on a black sidebar. Inlined, the mark takes
 * the colour of whatever it sits in, which is what lets the same file serve the
 * sidebar, the auth pages and any future light surface without variants.
 *
 * ⚠️ THE GEOMETRY IS DUPLICATED IN public/logo.svg, deliberately and unavoidably.
 * That file is the standalone asset (link previews, docs, anything outside React);
 * this is the one that inherits colour. There is no build step here that turns an
 * SVG file into a component, and adding vite-plugin-svgr to de-duplicate seven
 * coordinates would cost more than it saves. If the ridge is ever redrawn, BOTH
 * change — and public/logo-icon.svg is a third, deliberately different drawing.
 */
function Ridge({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      // Decorative everywhere it is used: every call site pairs it with the
      // "Kailaas OS" wordmark in text, so announcing it would just say the name
      // twice.
      aria-hidden
      className={className}
    >
      <polyline points="2.5,20.5 5,16.4 7.1,19.8 10.5,11 12,13.7 15.8,3.5 17.5,10.6" />
      {/* The tail, as a separate path so it can carry its own dash pattern. At 24px
          and below the dashes merge into a solid line — see the note in
          public/logo-icon.svg for why the favicon does not even try. */}
      <path d="M17.5 10.6 21.5 13.9" strokeDasharray="1 0.85" />
    </svg>
  )
}

/**
 * `outline` (the default) is the mark everywhere in the app: a bare ridge taking
 * its colour from whatever it sits in.
 *
 * `inverted` is the landing hero and NOTHING ELSE — the ridge knocked out of a
 * solid white tile. It is a variant rather than a new default because the
 * sidebar, the auth pages and the favicon all still want the outline: a white
 * block in the sidebar would read as a selected row, and the favicon is a
 * separate drawing again (public/logo-icon.svg).
 */
export function LogoMark({
  className,
  variant = 'outline',
}: {
  className?: string
  variant?: 'outline' | 'inverted'
}) {
  if (variant === 'inverted') {
    return (
      // `className` sizes the TILE here, not the ridge — the ridge is a fixed
      // share of it. 62.5% is the sidebar's own ratio (a size-5 mark in a size-8
      // tile), which is what keeps the ridge clear of the corners instead of
      // running into the radius.
      //
      // The box is one fixed square with no intrinsic content driving it, so it
      // reserves its space on the first frame and cannot shift later.
      <span
        aria-hidden
        className={cn(
          'grid size-8 shrink-0 place-items-center rounded-lg bg-white text-background',
          className,
        )}
      >
        <Ridge className="size-[62.5%]" />
      </span>
    )
  }

  return <Ridge className={cn('size-5', className)} />
}
