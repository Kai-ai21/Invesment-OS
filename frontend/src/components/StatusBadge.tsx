import { cn } from '@/lib/utils'
import type { ClaimStatus, ThesisStatus, Verdict } from '@/lib/api'

/** Everything this badge can render: thesis status, claim status, or an evidence verdict. */
export type BadgeStatus = ThesisStatus | ClaimStatus | Verdict

/**
 * One home for status → colour. Outlined style: the status colour drives both the
 * text and a 50%-opacity border, over a transparent background. Every value in the
 * backend's vocabulary (backend/domain/status.py and the verification verdicts) is
 * listed explicitly, so adding a status there surfaces as a type error here rather
 * than a silent grey badge.
 */
const STATUS_CLASSES: Record<BadgeStatus, string> = {
  // Thesis statuses
  strengthening: 'border-status-strengthening/50 text-status-strengthening',
  weakening: 'border-status-weakening/50 text-status-weakening',
  breaking: 'border-status-breaking/50 text-status-breaking',

  // Claim statuses ('weakening' and 'pending' are shared with the set above)
  strongly_supported: 'border-status-supported/50 text-status-supported',
  supported: 'border-status-supported/50 text-status-supported',
  broken: 'border-status-broken/50 text-status-broken',
  pending: 'border-status-pending/50 text-status-pending',

  // Evidence verdicts
  supports: 'border-status-supported/50 text-status-supported',
  contradicts: 'border-status-broken/50 text-status-broken',
  neutral: 'border-status-pending/50 text-status-pending',
}

/**
 * Outlined, uppercase, mono status pill. Colour is never the only signal — the
 * label always spells the status out (`whitespace-nowrap` keeps "STRONGLY
 * SUPPORTED" on one line).
 */
export function StatusBadge({
  status,
  className,
}: {
  status: BadgeStatus
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex w-fit shrink-0 items-center whitespace-nowrap rounded-[4px] border bg-transparent px-[9px] py-[3px] font-mono text-[10.5px] leading-none tracking-[0.08em] uppercase',
        STATUS_CLASSES[status] ?? STATUS_CLASSES.pending,
        className,
      )}
    >
      {status.replace(/_/g, ' ')}
    </span>
  )
}
