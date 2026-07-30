import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

// The `btn-sweep` class (defined in index.css) carries the Uiverse hover effect
// — a white ::before circle that grows and inverts the button via mix-blend
// difference — plus the primary's lift, press and icon spin, the disabled
// handling and the reduced-motion guard. It lives in CSS because a mix-blend
// pseudo-element sweep can't be expressed in Tailwind utilities, and because the
// lift needs DIFFERENT enter and leave durations, which one utility cannot state.
//
// NOTE there is no `transition-all duration-300` here any more. A utility sits in
// a later cascade layer than the `.btn-sweep` rules, so it silently overrode the
// asymmetric timing; every button transition is now declared in index.css and
// this class contributes none. Variant hovers below stay gated with
// `not-disabled:` so a button disabled mid-AI-call shows no hover feedback.
const buttonVariants = cva(
  "btn-sweep group/button inline-flex shrink-0 items-center justify-center rounded-full border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        // GLASS PRIMARY. Translucent white film rather than an opaque surface, a
        // 1px lit border, and the highlight/shadow stack from --btn-glass-*.
        //
        // The shadows are SHADOW UTILITIES rather than box-shadow in index.css so
        // that they compose with `focus-visible:ring-3` into a single box-shadow.
        // Declared in CSS they would be overridden by the ring utility the moment
        // the button took focus — and keyboard focus is exactly where the glass
        // and glow have to survive, since focus deliberately gets the glow but
        // not the sweep. Rest and hover/focus are separate tokens; the two hover
        // states carry the same value so they never disagree.
        default:
          "border-white/12 bg-white/8 text-text-primary backdrop-blur-md shadow-[var(--btn-glass-rest)] not-disabled:hover:border-white/20 not-disabled:hover:bg-white/14 not-disabled:hover:shadow-[var(--btn-glow)] focus-visible:shadow-[var(--btn-glow)]",
        // The ONE main action on a page — today only "New thesis". Same glass
        // recipe as `default` but heavier throughout: brighter highlight, a
        // deeper lift, and every duration 1.4x (see index.css).
        hero:
          "border-white/18 bg-white/12 text-text-primary backdrop-blur-md shadow-[var(--btn-hero-rest)] not-disabled:hover:border-white/28 not-disabled:hover:bg-white/18 not-disabled:hover:shadow-[var(--btn-hero-glow)] focus-visible:shadow-[var(--btn-hero-glow)]",
        // QUIET GLASS — outline and ghost. Pill and a faint lit edge only: no
        // falloff, no drop shadow, no lift, no glow. These sit beside primaries
        // constantly (Cancel next to Save, icon actions in a table row) and have
        // to stay obviously subordinate, so they get the shape and nothing else.
        outline:
          "border-white/12 bg-white/4 backdrop-blur-sm shadow-[var(--btn-glass-quiet)] not-disabled:hover:border-white/20 not-disabled:hover:bg-white/10 not-disabled:hover:text-foreground aria-expanded:bg-white/10 aria-expanded:text-foreground",
        secondary:
          "border-white/10 bg-white/10 text-secondary-foreground backdrop-blur-sm shadow-[var(--btn-glass-quiet)] not-disabled:hover:bg-white/16 aria-expanded:bg-white/12 aria-expanded:text-secondary-foreground",
        ghost:
          "border-white/8 not-disabled:hover:border-white/16 not-disabled:hover:bg-white/8 not-disabled:hover:text-foreground aria-expanded:bg-white/8 aria-expanded:text-foreground",
        // Tinted glass: the destructive hue carries the meaning, so it keeps its
        // own colour and takes only the quiet highlight rather than a white film.
        destructive:
          "border-destructive/25 bg-destructive/12 text-destructive backdrop-blur-sm shadow-[var(--btn-glass-quiet)] not-disabled:hover:border-destructive/40 not-disabled:hover:bg-destructive/22 focus-visible:border-destructive/40 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40",
        // Deliberately NOT glass. A link variant is text in a sentence; giving it
        // a pill, a border or a surface would make it a button.
        link: "text-primary underline-offset-4 not-disabled:hover:underline",
      },
      // Radii are all `rounded-full` now: the base sets it, and the sizes that
      // used to pin a specific radius keep it explicit so a stray `--radius-md`
      // change cannot un-pill one size. Horizontal padding is a notch wider than
      // before — a pill needs more room at the ends than a 10px-radius box, or
      // the label crowds the curve.
      size: {
        default:
          "h-8 gap-1.5 px-3.5 has-data-[icon=inline-end]:pr-2.5 has-data-[icon=inline-start]:pl-2.5",
        xs: "h-6 gap-1 rounded-full px-2.5 text-xs has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 rounded-full px-3 text-[0.8rem] has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 gap-1.5 px-4 has-data-[icon=inline-end]:pr-3 has-data-[icon=inline-start]:pl-3",
        icon: "size-8",
        "icon-xs": "size-6 rounded-full [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-7 rounded-full",
        "icon-lg": "size-9",
      },
    },
    // The hero's extra height and padding live HERE, not in the variant above.
    // cva emits base -> variant -> size -> compound, and `cn` resolves Tailwind
    // conflicts last-wins, so a variant-level `h-9 px-4` would be overridden by
    // the size axis's `h-8 px-2.5` for every size. Compound classes are appended
    // after both, so these win — and they keep winning whichever size is passed.
    compoundVariants: [
      {
        variant: "hero",
        class: "h-9 gap-2 px-5",
      },
    ],
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
