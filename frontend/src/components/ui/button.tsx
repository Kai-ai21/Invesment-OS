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
  "btn-sweep group/button inline-flex shrink-0 items-center justify-center rounded-lg border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        // Uiverse original look: dark base, white text.
        //
        // The glow is a SHADOW UTILITY rather than a box-shadow in index.css so
        // that it composes with `focus-visible:ring-3` into a single box-shadow.
        // Declared in CSS it would be overridden by the ring utility the moment
        // the button took focus — and keyboard focus is exactly where the glow
        // has to survive, since focus deliberately gets the glow but not the
        // sweep. Both states carry the same value so the two never disagree.
        default:
          "bg-surface-raised text-text-primary not-disabled:hover:bg-[color-mix(in_oklch,var(--surface-raised),var(--foreground)_8%)] not-disabled:hover:shadow-[var(--btn-glow)] focus-visible:shadow-[var(--btn-glow)]",
        // The ONE main action on a page — today only "New thesis". Same palette
        // and the same hover contract as `default`, but heavier: a resting glow,
        // a deeper lift, and every duration 1.4x (see index.css).
        //
        // The resting shadow is what makes this variant different at a glance.
        // Like the hover glow it is a utility, not CSS, so it composes with
        // `focus-visible:ring-3` instead of being overridden by it.
        hero:
          "bg-surface-raised text-text-primary shadow-[var(--btn-hero-rest)] not-disabled:hover:bg-[color-mix(in_oklch,var(--surface-raised),var(--foreground)_8%)] not-disabled:hover:shadow-[var(--btn-hero-glow)] focus-visible:shadow-[var(--btn-hero-glow)]",
        outline:
          "border-border bg-background not-disabled:hover:bg-muted not-disabled:hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground dark:border-input dark:bg-input/30 dark:not-disabled:hover:bg-input/50",
        secondary:
          "bg-secondary text-secondary-foreground not-disabled:hover:bg-[color-mix(in_oklch,var(--secondary),var(--foreground)_5%)] aria-expanded:bg-secondary aria-expanded:text-secondary-foreground",
        ghost:
          "not-disabled:hover:bg-muted not-disabled:hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground dark:not-disabled:hover:bg-muted/50",
        destructive:
          "bg-destructive/10 text-destructive not-disabled:hover:bg-destructive/20 focus-visible:border-destructive/40 focus-visible:ring-destructive/20 dark:bg-destructive/20 dark:not-disabled:hover:bg-destructive/30 dark:focus-visible:ring-destructive/40",
        link: "text-primary underline-offset-4 not-disabled:hover:underline",
      },
      size: {
        default:
          "h-8 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        xs: "h-6 gap-1 rounded-[min(var(--radius-md),10px)] px-2 text-xs in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 rounded-[min(var(--radius-md),12px)] px-2.5 text-[0.8rem] in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        icon: "size-8",
        "icon-xs":
          "size-6 rounded-[min(var(--radius-md),10px)] in-data-[slot=button-group]:rounded-lg [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-7 rounded-[min(var(--radius-md),12px)] in-data-[slot=button-group]:rounded-lg",
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
        class: "h-9 gap-2 px-4",
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
