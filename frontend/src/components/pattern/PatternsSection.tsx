import { useCallback, useState } from 'react'
import { Loader2, Sparkles } from 'lucide-react'

import { EmptyIllustration } from '@/components/EmptyIllustration'
import { PatternCard } from '@/components/pattern/PatternCard'
import { Count } from '@/components/Count'
import { ErrorState } from '@/components/ErrorState'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAsync } from '@/hooks/useAsync'
import { generatePatterns, listPatterns, type Pattern, type PostMortem } from '@/lib/api'
import { describeError } from '@/lib/errors'

/**
 * Mirrors MINIMUM_POST_MORTEMS in backend/services/pattern_service.py. Duplicated
 * because the count is not exposed on a GET — the backend only reports it inside the
 * `reason` string returned by a generate. Held here so the "not enough yet" state can
 * be shown BEFORE the user presses a button that would only tell them the same thing.
 * If the backend constant changes, this must change with it.
 */
const MINIMUM_REFLECTIONS = 3

export function PatternsSection({
  postMortems,
  loadingPostMortems,
}: {
  /** The reflections behind the patterns — supplies each source's written response,
   *  and the answered count that decides the "not enough yet" state. */
  postMortems: PostMortem[]
  loadingPostMortems: boolean
}) {
  const load = useCallback(() => listPatterns(), [])
  const { data, error, loading, refresh, reload } = useAsync<Pattern[]>(load)

  const [analysing, setAnalysing] = useState(false)
  const [analyseError, setAnalyseError] = useState<string | null>(null)
  // Set only by a generate that came back empty. Distinguishes "analysed, found
  // nothing" from "never analysed" — an empty array alone cannot tell them apart.
  const [emptyReason, setEmptyReason] = useState<string | null>(null)

  const patterns = data ?? []
  const answeredCount = postMortems.filter(
    (item) => item.user_response !== null,
  ).length
  const belowMinimum = answeredCount < MINIMUM_REFLECTIONS

  const handleAnalyse = useCallback(async () => {
    if (analysing) return
    setAnalysing(true)
    setAnalyseError(null)
    try {
      const result = await generatePatterns()
      // An empty result is a legitimate answer, not a failure — the backend explains
      // which kind of empty it is.
      setEmptyReason(result.patterns.length === 0 ? result.reason : null)
      refresh()
    } catch (cause: unknown) {
      setAnalyseError(describeError(cause, 'your patterns').detail)
    } finally {
      setAnalysing(false)
    }
  }, [analysing, refresh])

  return (
    <section className="mb-12">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-xl tracking-[0.01em] text-text-primary">
          Patterns
          <Count value={patterns.length} />
        </h2>
        <Button
          variant="outline"
          onClick={handleAnalyse}
          // Pointless below the minimum: it would spend a round trip to say
          // exactly what the empty state already says.
          disabled={analysing || belowMinimum || loadingPostMortems}
          title={
            belowMinimum
              ? `Available after ${MINIMUM_REFLECTIONS} answered reflections`
              : undefined
          }
        >
          {analysing ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <Sparkles aria-hidden />
          )}
          {analysing ? 'Analysing…' : 'Analyse my reflections'}
        </Button>
      </header>

      {analysing && (
        <p className="mb-3 text-sm text-text-secondary">
          Reading back through your reflections. This takes a few seconds.
        </p>
      )}

      {analyseError && (
        <p role="alert" className="mb-3 text-sm text-status-broken">
          {analyseError}
        </p>
      )}

      {loading ? (
        <Skeleton className="h-59 w-full rounded-xl" />
      ) : error ? (
        <ErrorState error={error} subject="your patterns" onRetry={reload} />
      ) : patterns.length > 0 ? (
        <div className="flex flex-col gap-4">
          {patterns.map((pattern) => (
            <PatternCard
              key={pattern.id}
              pattern={pattern}
              postMortems={postMortems}
              onDismissed={refresh}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          belowMinimum={belowMinimum}
          answeredCount={answeredCount}
          reason={emptyReason}
        />
      )}
    </section>
  )
}

/**
 * THREE distinct empty states, deliberately not collapsed into one. "You haven't
 * written enough yet", "we looked and found nothing", and "we haven't looked yet" are
 * different facts, and showing the wrong one would either nag the user for something
 * they cannot do or imply a verdict that was never reached.
 */
function EmptyState({
  belowMinimum,
  answeredCount,
  reason,
}: {
  belowMinimum: boolean
  answeredCount: number
  reason: string | null
}) {
  // 1. Not enough material. Explains the mechanism rather than reporting absence, so
  // the user knows this is a threshold and not a bug.
  if (belowMinimum) {
    return (
      <EmptyCard
        title={`Patterns appear after ${MINIMUM_REFLECTIONS} reflections. You have ${answeredCount}.`}
        body="Patterns need enough material to be real — across two reflections, any two stories look like a theme."
      />
    )
  }

  // 2. Analysed, found nothing. A real, honest result, not a failure.
  if (reason) {
    return (
      <EmptyCard
        title="No recurring patterns yet"
        body="Your reflections so far don't show a consistent theme. That is a genuine result, not a missing one."
      />
    )
  }

  // 3. Not yet analysed.
  return (
    <EmptyCard
      title="Ready to analyse"
      body={`You have ${answeredCount} answered reflections. Analyse them to look for recurring behaviour.`}
    />
  )
}

function EmptyCard({ title, body }: { title: string; body: string }) {
  return (
    // 48px, like every other empty state — it was the app's one 32px card, which
    // is why it never quite matched the ones on Theses, Alerts or Portfolio.
    <Card className="[--card-spacing:--spacing(12)]">
      <div className="flex flex-col items-center gap-1 px-(--card-spacing) text-center">
        {/* One mark for all three of the states above. They differ in what they
            SAY — not enough material, looked and found nothing, not looked yet —
            and three different graphics for one subject would read as three
            different features. */}
        <EmptyIllustration variant="patterns" className="mb-3" />
        <p className="font-display text-base tracking-[0.01em] text-text-primary">
          {title}
        </p>
        <p className="max-w-lg text-sm text-text-secondary">{body}</p>
      </div>
    </Card>
  )
}

