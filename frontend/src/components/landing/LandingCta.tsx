import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router'

/**
 * The landing page's call to action: a gradient-border pill whose rim lights up
 * and travels on hover.
 *
 * TWO ELEMENTS, ONE FOCUSABLE. The outer <Link> carries the gradient and all the
 * interaction state; the inner <span> is the opaque face that masks the gradient
 * down to a 1.5px rim. All of that lives in index.css under `.landing-cta` —
 * it needs a registered @property to animate the gradient angle, which Tailwind
 * utilities cannot express.
 *
 * A LINK, not a button: this goes somewhere, so it should middle-click,
 * right-click and open in a new tab like any other link.
 *
 * This replaced a WebGL specular button. That component's rounded shape existed
 * only because a fragment shader discarded the corners of a square, unclipped
 * canvas, so any frame that did not render as expected exposed the rectangle —
 * and it pulled in `ogl` for a single button. Both are now gone.
 */
export function LandingCta() {
  return (
    <Link
      to="/theses"
      className="landing-cta focus-visible:ring-3 focus-visible:ring-ring/60 focus-visible:outline-none"
    >
      <span className="landing-cta-inner">
        Open dashboard
        {/* aria-hidden: the arrow is direction, not information — the label
            already says where this goes. */}
        <ArrowRight className="landing-cta-arrow size-4" aria-hidden />
      </span>
    </Link>
  )
}
