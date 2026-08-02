import { RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { describeError } from '@/lib/errors'
import { cn } from '@/lib/utils'

/**
 * The failure state for anything that loads.
 *
 * ONE component, because there were six byte-identical copies of it across the
 * pages differing only in their title, and each one rendered `error.message`
 * straight to the screen — which is how a reader came to be shown a request path
 * and an HTTP status. The wording now comes from `describeError`; see the note
 * there for what those messages used to say.
 *
 * ⚠️ RETRY IS CONDITIONAL. A 404 or a rejected input cannot be fixed by asking
 * again, and offering a button that is guaranteed to fail is worse than offering
 * none — so `describeError` decides, not the call site.
 */
export function ErrorState({
  error,
  subject,
  onRetry,
  bare = false,
  className,
}: {
  error: unknown
  /** Noun phrase naming what the user was trying to see: "your theses", "the news". */
  subject: string
  onRetry?: () => void
  /** Drops the Card wrapper, for slots that are already a panel (the news list). */
  bare?: boolean
  className?: string
}) {
  const { title, detail, canRetry } = describeError(error, subject)

  const body = (
    <div
      className={cn(
        'flex flex-col items-start gap-4',
        !bare && 'px-(--card-spacing)',
      )}
      role="alert"
    >
      <div>
        <p className="text-sm font-medium text-text-primary">{title}</p>
        <p className="mt-1 text-sm text-status-broken">{detail}</p>
      </div>
      {canRetry && onRetry && (
        <Button variant="outline" onClick={onRetry}>
          <RefreshCw aria-hidden />
          Retry
        </Button>
      )}
    </div>
  )

  if (bare) return <div className={cn('py-6', className)}>{body}</div>
  return <Card className={className}>{body}</Card>
}
