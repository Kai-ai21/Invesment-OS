import { Loader2, RefreshCw, X } from 'lucide-react'

import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { MAX_CHECK_LIMIT, type CheckNowState } from '@/hooks/useCheckNow'

const LIMIT_OPTIONS = Array.from({ length: MAX_CHECK_LIMIT }, (_, i) => i + 1)

/** Trigger + filing-count control. Sits in the page header. */
export function CheckNowControls({ check }: { check: CheckNowState }) {
  return (
    <div className="flex items-center gap-2">
      <Select
        value={String(check.limit)}
        onValueChange={(value) => check.setLimit(Number(value))}
        disabled={check.pending}
      >
        <SelectTrigger size="sm" className="w-28" aria-label="Filings to check">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {LIMIT_OPTIONS.map((n) => (
            <SelectItem key={n} value={String(n)}>
              {n} {n === 1 ? 'filing' : 'filings'}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Button variant="outline" onClick={check.run} disabled={check.pending}>
        {check.pending ? (
          <Loader2 className="animate-spin" aria-hidden />
        ) : (
          <RefreshCw aria-hidden />
        )}
        {check.pending ? 'Fetching filings from SEC…' : 'Check now'}
      </Button>
    </div>
  )
}

/** Pending notice, result summary, or error. Renders below the page header. */
export function CheckNowResult({ check }: { check: CheckNowState }) {
  if (check.pending) {
    return (
      <Card className="[--card-spacing:--spacing(5)]">
        <div className="flex items-start gap-3 px-(--card-spacing)">
          <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin text-text-muted" aria-hidden />
          <div>
            <p className="text-sm text-text-primary">Fetching filings from SEC…</p>
            <p className="mt-1 text-sm text-text-secondary">
              Each filing is then read against every claim, one AI call at a time.
              This can take a while — leave the page open.
            </p>
          </div>
        </div>
      </Card>
    )
  }

  if (check.error) {
    return (
      <Card className="[--card-spacing:--spacing(5)]">
        <div className="flex items-start justify-between gap-4 px-(--card-spacing)">
          <div>
            <p className="text-sm font-medium text-text-primary">Check failed</p>
            <p className="mt-1 text-sm text-status-broken">{check.error}</p>
          </div>
          <DismissButton onClick={check.dismiss} />
        </div>
      </Card>
    )
  }

  if (!check.result) return null

  const { result } = check
  const statusChanged = result.status_before !== result.status_after

  return (
    <Card className="[--card-spacing:--spacing(5)]">
      <div className="flex flex-col gap-4 px-(--card-spacing)">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-text-primary">
              Checked {result.ticker}
            </p>
            <p className="mt-1 text-sm text-text-secondary">
              {result.filings_found === 0
                ? 'No recent filings found on SEC EDGAR.'
                : `${result.filings_found} recent ${
                    result.filings_found === 1 ? 'filing' : 'filings'
                  } found.`}{' '}
              {result.total_evidence_created === 0
                ? 'No new evidence — nothing in them bore on your claims.'
                : `${result.total_evidence_created} new evidence ${
                    result.total_evidence_created === 1 ? 'event' : 'events'
                  }.`}
            </p>
          </div>
          <DismissButton onClick={check.dismiss} />
        </div>

        {statusChanged && (
          <div className="flex flex-wrap items-center gap-2 rounded-lg bg-surface-raised px-4 py-3">
            <span className="text-sm font-medium text-text-primary">Status changed</span>
            <StatusBadge status={result.status_before} />
            <span aria-hidden className="text-text-muted">
              →
            </span>
            <StatusBadge status={result.status_after} />
          </div>
        )}

        {result.checked.length > 0 && (
          <div>
            <p className="mb-2 text-xs tracking-wide text-text-muted uppercase">
              Filings checked
            </p>
            <ul className="flex flex-col gap-1.5">
              {result.checked.map((filing, i) => (
                <li
                  key={`${filing.title}-${i}`}
                  className="flex items-baseline justify-between gap-4 text-sm"
                >
                  <span className="text-text-secondary">{filing.title}</span>
                  <span className="shrink-0 text-text-muted">
                    {filing.evidence_created === 0
                      ? 'no evidence'
                      : `${filing.evidence_created} ${
                          filing.evidence_created === 1 ? 'event' : 'events'
                        }`}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {result.skipped.length > 0 && (
          <div>
            <p className="mb-2 text-xs tracking-wide text-status-weakening uppercase">
              Skipped ({result.skipped.length})
            </p>
            <ul className="flex flex-col gap-1.5">
              {result.skipped.map((filing, i) => (
                <li key={`${filing.title}-${i}`} className="text-sm">
                  <span className="text-text-secondary">{filing.title}</span>
                  <span className="text-text-muted"> — {filing.reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {check.stale && (
          <p className="text-sm text-status-weakening">
            The check finished, but reloading the thesis failed — what's shown below
            may be out of date. Reload the page to see current statuses.
          </p>
        )}
      </div>
    </Card>
  )
}

function DismissButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      onClick={onClick}
      aria-label="Dismiss result"
      className="shrink-0 text-text-muted hover:text-text-primary"
    >
      <X aria-hidden />
    </Button>
  )
}
