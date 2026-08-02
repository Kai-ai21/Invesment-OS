import { Tooltip } from '@/components/ui/tooltip'
import { formatExact, formatRelative, toMachineDate } from '@/lib/format'
import { cn } from '@/lib/utils'

/**
 * A timestamp: relative in the row, exact on hover.
 *
 * Relative is what you want while scanning ("2 days ago" answers "is this recent?"
 * without arithmetic), and exact is what you want the moment you care ("which
 * Tuesday?"). Showing only one forces the reader to pick in advance.
 *
 * ⚠️ THE TOOLTIP SHOWS THE CORRECTED TIME. The backend stores UTC instants in a
 * naive column and serialises them without a zone designator, so `new Date()` would
 * read them as local and be wrong by the viewer's offset — see parseBackendDate in
 * lib/format. Both strings here go through it, and so does the `dateTime`
 * attribute, which is the value anything machine-readable will pick up.
 *
 * NOT for date-only values. A filing date or a purchase date is a calendar date
 * with no time and no zone; rendering one here would invent an hour and then
 * confidently display it. Those use formatPlainDate.
 */
export function RelativeTime({
  iso,
  prefix,
  className,
}: {
  iso: string
  /** Read aloud with the time, e.g. "checked" -> "checked 2 days ago". */
  prefix?: string
  className?: string
}) {
  const machine = toMachineDate(iso)

  return (
    <Tooltip content={formatExact(iso)}>
      <time
        // Omitted rather than emitted empty when the value would not parse.
        dateTime={machine || undefined}
        className={cn('cursor-help', className)}
      >
        {prefix ? `${prefix} ` : ''}
        {formatRelative(iso)}
      </time>
    </Tooltip>
  )
}
