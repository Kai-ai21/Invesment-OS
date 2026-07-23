import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ClaimStatus, ThesisStatus, Verdict } from '@/lib/api'

/** Everything this badge can render: thesis status, claim status, or an evidence verdict. */
export type BadgeStatus = ThesisStatus | ClaimStatus | Verdict

/**
 * One home for status → colour. Every value in the backend's vocabulary
 * (backend/domain/status.py and the verification verdicts) is listed explicitly,
 * so adding a status there surfaces as a type error here rather than a silent
 * grey badge.
 */
const STATUS_CLASSES: Record<BadgeStatus, string> = {
  // Thesis statuses
  strengthening: 'bg-status-strengthening/10 text-status-strengthening',
  weakening: 'bg-status-weakening/10 text-status-weakening',
  breaking: 'bg-status-breaking/10 text-status-breaking',

  // Claim statuses ('weakening' and 'pending' are shared with the set above)
  strongly_supported: 'bg-status-supported/10 text-status-supported',
  supported: 'bg-status-supported/10 text-status-supported',
  broken: 'bg-status-broken/10 text-status-broken',
  pending: 'bg-status-pending/10 text-status-pending',

  // Evidence verdicts
  supports: 'bg-status-supported/10 text-status-supported',
  contradicts: 'bg-status-broken/10 text-status-broken',
  neutral: 'bg-status-pending/10 text-status-pending',
}

/** Colour is never the only signal — the label always spells the status out. */
export function StatusBadge({
  status,
  className,
}: {
  status: BadgeStatus
  className?: string
}) {
  return (
    <Badge
      className={cn(
        STATUS_CLASSES[status] ?? STATUS_CLASSES.pending,
        'capitalize',
        className,
      )}
    >
      {status.replace(/_/g, ' ')}
    </Badge>
  )
}
