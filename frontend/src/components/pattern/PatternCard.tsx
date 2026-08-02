import { useState } from 'react'
import { ChevronDown, ChevronRight, Loader2, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { describeError } from '@/lib/errors'
import { dismissPattern, type Pattern, type PostMortem } from '@/lib/api'

/**
 * One observed pattern.
 *
 * Deliberately NOT colour-coded. A pattern is an observation about the user's own
 * past behaviour, not a verdict on it — tinting it red or green would turn a
 * description into a judgement, which is exactly what the prompt forbids the model
 * from doing. Everything here is neutral text on the standard card surface.
 */
export function PatternCard({
  pattern,
  postMortems,
  onDismissed,
}: {
  pattern: Pattern
  /** Used to show each source's written response — the API's PatternSource carries
   *  the ticker and question but not the answer, and this page already has them. */
  postMortems: PostMortem[]
  onDismissed?: () => void
}) {
  const [showSources, setShowSources] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [dismissing, setDismissing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [gone, setGone] = useState(false)

  const responseById = new Map(
    postMortems.map((item) => [item.id, item.user_response]),
  )

  async function handleDismiss() {
    if (dismissing) return
    setDismissing(true)
    setError(null)
    try {
      await dismissPattern(pattern.id)
      // No undo offered: dismissing is a considered judgement (it asks first), and
      // regenerating brings back anything still true.
      setGone(true)
      onDismissed?.()
    } catch (cause: unknown) {
      setError(describeError(cause, 'this pattern').detail)
      setDismissing(false)
    }
  }

  if (gone) return null

  return (
    <Card>
      <div className="flex flex-col gap-4 px-(--card-spacing)">
        <div className="flex items-start justify-between gap-4">
          {/* Serif: this is prose about the user, same treatment as their own writing. */}
          <p className="font-serif text-base leading-[1.5] text-text-primary">
            {pattern.statement}
          </p>
          {!confirming && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setConfirming(true)}
              aria-label="Dismiss this pattern"
              className="shrink-0 text-text-muted hover:text-text-primary"
            >
              <X aria-hidden />
            </Button>
          )}
        </div>

        {error && (
          <p role="alert" className="text-sm text-status-broken">
            {error}
          </p>
        )}

        {/* Confirm before dismissing: rejecting an observation about yourself is a
            judgement, not a misclick. */}
        {confirming && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-text-secondary">Dismiss this pattern?</span>
            <Button size="sm" onClick={handleDismiss} disabled={dismissing}>
              {dismissing && <Loader2 className="animate-spin" aria-hidden />}
              Dismiss
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setConfirming(false)}
              disabled={dismissing}
              className="text-text-secondary"
            >
              Cancel
            </Button>
          </div>
        )}

        {/* The evidence is ALWAYS one click away. A claim about someone's behaviour
            that they cannot trace back to what they actually wrote is not something
            this product should ever show. */}
        <div>
          <button
            type="button"
            onClick={() => setShowSources((open) => !open)}
            aria-expanded={showSources}
            className="flex items-center gap-1.5 rounded-lg text-sm text-text-secondary transition-colors hover:text-text-primary focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            {showSources ? (
              <ChevronDown className="size-4" aria-hidden />
            ) : (
              <ChevronRight className="size-4" aria-hidden />
            )}
            Based on {pattern.sources.length}{' '}
            {pattern.sources.length === 1 ? 'reflection' : 'reflections'}
          </button>

          {showSources && (
            <ul className="mt-3 flex flex-col gap-4 border-l-2 border-border pl-4">
              {pattern.sources.map((source) => (
                <li key={source.post_mortem_id} className="flex flex-col gap-1">
                  <span className="font-mono text-xs tracking-[0.08em] text-text-secondary uppercase">
                    {source.ticker}
                  </span>
                  {source.prompt_question && (
                    <p className="font-serif text-sm leading-[1.5] text-text-secondary">
                      {source.prompt_question}
                    </p>
                  )}
                  <p className="font-serif text-sm leading-relaxed whitespace-pre-wrap text-text-muted">
                    {responseById.get(source.post_mortem_id) ??
                      '(this reflection is no longer available)'}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Card>
  )
}
