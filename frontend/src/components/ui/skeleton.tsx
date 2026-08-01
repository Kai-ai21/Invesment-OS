import { cn } from "@/lib/utils"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      // skeleton-shimmer replaces the stock animate-pulse: a sweep says "loading"
      // the way a whole box breathing in and out does not, and it composites
      // rather than repaints. Definition and the reduced-motion opt-out are in
      // index.css.
      className={cn("skeleton-shimmer rounded-md bg-muted", className)}
      {...props}
    />
  )
}

export { Skeleton }
