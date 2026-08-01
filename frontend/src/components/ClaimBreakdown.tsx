import { statusColor } from '@/components/StatusBadge'
import { Tooltip } from '@/components/ui/tooltip'
import type { Claim, ClaimStatus } from '@/lib/api'
import { cn } from '@/lib/utils'

/**
 * The order claims are shown in, worst first.
 *
 * ⚠️ NOT the order they were written in. A thesis with one broken claim among six
 * healthy ones should read as having a broken claim, and a bar that buries the
 * red segment in the middle makes that a hunt. Worst-first also means the eye
 * lands on the left edge and immediately knows the answer.
 *
 * `strongly_supported` and `supported` are deliberately ONE segment: at this size
 * the distinction is a shade of the same green, and splitting it would imply a
 * precision the bar cannot carry. The count reads "supported" for both.
 */
const ORDER: ClaimStatus[] = [
  'broken',
  'weakening',
  'strongly_supported',
  'supported',
  'pending',
]

const GROUP_LABEL: Record<ClaimStatus, string> = {
  broken: 'broken',
  weakening: 'weakening',
  strongly_supported: 'supported',
  supported: 'supported',
  pending: 'pending',
}

/**
 * A segmented bar: how a thesis's claims are doing, at a glance.
 *
 * Colour comes from the same STATUS_TOKEN map as every badge and spine, so a red
 * segment here is the identical red to a BROKEN pill. Colour is not the only
 * signal — the tooltip spells out every count in words, and the card carries the
 * claim total in text beside it.
 */
export function ClaimBreakdown({
  claims,
  className,
}: {
  claims: Claim[]
  className?: string
}) {
  if (claims.length === 0) return null

  // Grouped by the LABEL, so the two supported statuses merge into one segment.
  const counts = new Map<string, { count: number; status: ClaimStatus }>()
  for (const status of ORDER) {
    const matching = claims.filter((claim) => claim.status === status)
    if (matching.length === 0) continue
    const label = GROUP_LABEL[status]
    const existing = counts.get(label)
    counts.set(label, {
      count: (existing?.count ?? 0) + matching.length,
      // First status wins the colour, and ORDER is worst-first, so a merged
      // group takes the more serious of the two — which for the supported pair
      // is the same token anyway.
      status: existing?.status ?? status,
    })
  }

  const segments = [...counts.entries()]
  const summary = segments
    .map(([label, { count }]) => `${count} ${label}`)
    .join(', ')

  return (
    <Tooltip
      content={`${claims.length} ${claims.length === 1 ? 'claim' : 'claims'}: ${summary}`}
    >
      <span
        className={cn('inline-flex h-1 w-16 shrink-0 gap-px overflow-hidden rounded-full', className)}
      >
        {segments.map(([label, { count, status }]) => (
          <span
            key={label}
            // flex-grow by count, so a segment's WIDTH is its share of the
            // claims — the bar is a proportion, not a legend.
            style={{ flexGrow: count, backgroundColor: statusColor(status) }}
            // The bar as a whole is described by the tooltip; the pieces are
            // decoration and must not be announced one at a time.
            aria-hidden
          />
        ))}
        <span className="sr-only">{summary}</span>
      </span>
    </Tooltip>
  )
}
