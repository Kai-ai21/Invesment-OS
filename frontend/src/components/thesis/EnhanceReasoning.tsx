import { useState } from 'react'
import { Check, Loader2, Sparkles, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { enhanceReasoning } from '@/lib/api'

/** Matches the backend's MIN_REASONING_LENGTH — below this there is nothing to
 *  sharpen, and asking would invite the model to invent a thesis. */
const MIN_REASONING_LENGTH = 15

type Outcome =
  | { kind: 'proposal'; enhanced: string }
  | { kind: 'already-specific' }
  | { kind: 'error'; message: string }

/**
 * Optional "sharpen my wording" action for the reasoning field.
 *
 * ⚠️ TWO THINGS THIS MUST NEVER DO.
 *
 * It never overwrites what the user wrote without them saying so. The rewrite
 * arrives as a PROPOSAL shown beside the original, and nothing changes until
 * "Use this" is pressed — the original stays on screen the whole time, so there
 * is no state in which their words have been replaced by a machine's without
 * their consent and no way back.
 *
 * And it is never required. Create thesis does not call this, does not wait for
 * it, and is not blocked by it failing. Every error here is inline and advisory;
 * the form submits exactly as it would if this component did not exist.
 */
export function EnhanceReasoning({
  ticker,
  reasoning,
  onAccept,
}: {
  ticker: string
  reasoning: string
  /** Called only when the user explicitly accepts the rewrite. */
  onAccept: (enhanced: string) => void
}) {
  const [pending, setPending] = useState(false)
  const [outcome, setOutcome] = useState<Outcome | null>(null)

  const tooShort = reasoning.trim().length < MIN_REASONING_LENGTH

  async function handleEnhance() {
    if (pending) return
    setPending(true)
    setOutcome(null)
    try {
      const result = await enhanceReasoning(ticker.trim() || 'this company', reasoning)
      setOutcome(
        result.unchanged
          ? // Said plainly. The alternative — showing their own text back as though
            // it were an improvement — would be a small lie the user could catch.
            { kind: 'already-specific' }
          : { kind: 'proposal', enhanced: result.enhanced },
      )
    } catch (cause: unknown) {
      setOutcome({
        kind: 'error',
        message: cause instanceof Error ? cause.message : String(cause),
      })
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        {/* Ghost, not primary: the page's primary action is Create thesis, and a
            second filled button beside it would compete for that role. */}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleEnhance}
          disabled={pending || tooShort}
          title={tooShort ? 'Write a little more first' : undefined}
        >
          {pending ? <Loader2 className="animate-spin" aria-hidden /> : <Sparkles aria-hidden />}
          {pending ? 'Sharpening…' : 'Enhance'}
        </Button>

        {pending && (
          <span className="text-xs text-text-muted">
            Tightening your wording — this takes a few seconds.
          </span>
        )}

        {!pending && outcome?.kind === 'already-specific' && (
          <span className="text-xs text-text-secondary">
            Your reasoning is already specific enough.
          </span>
        )}

        {!pending && outcome?.kind === 'error' && (
          // Inline and advisory. Never a blocking dialog, and never styled like a
          // validation failure — nothing the user did is wrong.
          <span role="alert" className="text-xs text-status-broken">
            Couldn't enhance right now. Your reasoning is unaffected.
          </span>
        )}
      </div>

      {outcome?.kind === 'proposal' && (
        <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface-raised/60 p-4">
          <div className="flex flex-col gap-1.5">
            <p className="font-mono text-[11px] tracking-[0.08em] text-text-muted uppercase">
              Suggested wording
            </p>
            {/* Serif, matching how reasoning is displayed on the thesis page, so
                the user is reading it in the form it will actually take. */}
            <p className="font-serif text-[15px] leading-relaxed whitespace-pre-wrap text-text-primary">
              {outcome.enhanced}
            </p>
          </div>

          <p className="text-xs text-text-muted">
            Only your wording was tightened — no new claims, figures or reasons were
            added. Your original is still in the box above.
          </p>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => {
                onAccept(outcome.enhanced)
                setOutcome(null)
              }}
            >
              <Check aria-hidden />
              Use this
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setOutcome(null)}
            >
              <X aria-hidden />
              Keep mine
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
