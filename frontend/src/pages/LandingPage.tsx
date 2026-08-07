import { LogoMark } from '@/components/LogoMark'
import { NeuralBackground } from '@/components/effects/NeuralBackground'
import { ShinyText } from '@/components/effects/ShinyText'
import { LandingCta } from '@/components/landing/LandingCta'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'

/**
 * The only route with particles. Everything past the CTA is flat, functional
 * chrome.
 */
export function LandingPage() {
  useDocumentTitle(null)
  return (
    <div className="relative h-screen overflow-hidden bg-background">
      <div className="absolute inset-0">
        <NeuralBackground
          color="#ffffff"
          particleCount={400}
          speed={0.7}
          trailOpacity={0.12}
          backgroundColor="#0f1115"
        />
      </div>

      {/* Vignette so the centred text keeps its contrast wherever the field
          happens to be dense. */}
      <div
        aria-hidden
        className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(15,17,21,0.55)_0%,rgba(15,17,21,0.15)_45%,rgba(15,17,21,0.7)_100%)]"
      />

      <main className="page-enter relative flex h-full flex-col items-center justify-center gap-6 px-6 text-center">
        {/* Mark and wordmark are ONE unit, which is the whole reason for this
            wrapper. As siblings of the tagline they would inherit the stack's
            gap-6 and sit as far from the wordmark as the tagline does, reading as
            three stacked things instead of a lockup with a caption under it. The
            tighter gap-5 groups them; the outer gap-6 still separates the pair
            from the tagline, so nothing below here moves. */}
        <div className="flex flex-col items-center gap-5">
          {/* The same inlined component the sidebar and auth pages use — NOT a
              copy, and not <img src="/logo.svg">, which could not inherit colour
              (see LogoMark). Only the size and colour change here.

              Sized on a shallower track than the wordmark (6vw against its 9vw)
              so the gap between them widens with the viewport and the mark stays
              subordinate: 72px against an 88px wordmark on a wide desktop. The
              2.5rem floor is what keeps it from overtaking the wordmark on a
              phone, where the wordmark has bottomed out at its own 2.5rem floor
              and a mark held at 56px would be the biggest thing on screen.

              No entry animation, deliberately. The page-enter fade on <main>
              already carries the whole hero in as one piece; a second, separate
              fade here would re-introduce exactly the staggered-arrival feel the
              font preloading was meant to remove. */}
          <LogoMark
            className="size-[clamp(2.5rem,6vw,4.5rem)] text-text-primary"
          />

          {/* Display font at WEIGHT 400 — `font-normal` is explicit rather than
              inherited, because Righteous ships a single weight and anything above
              400 makes the browser synthesise a bold by smearing the outlines.

              clamp() rather than breakpoint steps: the wordmark is now large enough
              that a fixed size would overflow a narrow phone. 9vw is the preferred
              track; the 2.5rem floor keeps it readable at 320px, and the 5.5rem
              ceiling is where it stops growing on a wide desktop (~1.5x the 3.75rem
              it used to reach). Positive tracking stays — Righteous's letterforms
              are wide and crowd at negative values. */}
          <h1 className="font-display text-[clamp(2.5rem,9vw,5.5rem)] leading-[1.05] font-normal tracking-[0.01em]">
            <ShinyText text="Kailaas OS" color="#b5b5b5" shineColor="#ffffff" speed={3} />
          </h1>
        </div>

        {/* Scaled with the wordmark but on a much shallower curve, so the gap
            between them widens as the screen grows and the tagline stays
            unmistakably secondary rather than competing. */}
        <p className="font-subtitle max-w-xl text-[clamp(1rem,2.2vw,1.375rem)] leading-snug text-text-secondary">
          Remembers why you invested. Checks if it still holds.
        </p>

        <div className="mt-2">
          <LandingCta />
        </div>
      </main>
    </div>
  )
}
