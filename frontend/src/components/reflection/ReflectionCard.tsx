import { useCallback, useEffect, useState } from 'react'
import { Loader2, Trash2 } from 'lucide-react'

import { CompanyLogo } from '@/components/CompanyLogo'
import { StatusBadge } from '@/components/StatusBadge'
import { StatusSpine } from '@/components/StatusSpine'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import {
  answerPostMortem,
  deletePostMortem,
  generateQuestion,
  type PostMortem,
} from '@/lib/api'
import { formatRelative } from '@/lib/format'

/**
 * Asked for a MANUALLY opened reflection. There is no broken claim to be specific
 * about, and the backend deliberately refuses to invent a generic AI question, so the
 * UI supplies a fixed one rather than calling the model.
 */
const MANUAL_QUESTION = "What's changed in your thinking about this thesis?"

function isManual(postMortem: PostMortem): boolean {
  return postMortem.broken_claim_id === null
}

export function ReflectionCard({
  postMortem,
  onChanged,
}: {
  postMortem: PostMortem
  /** Called after save or delete so the container can refetch and the sidebar
   *  badge can be re-counted. */
  onChanged?: () => void
}) {
  // Local copy so a save updates in place without waiting for a parent refetch.
  const [item, setItem] = useState(postMortem)
  const [dismissed, setDismissed] = useState(false)
  const [response, setResponse] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Question generation, for automatic post-mortems only.
  const [generating, setGenerating] = useState(false)
  const manual = isManual(item)
  const needsQuestion = !manual && item.prompt_question === null && !item.user_response

  useEffect(() => setItem(postMortem), [postMortem])

  useEffect(() => {
    if (!needsQuestion) return
    let cancelled = false
    setGenerating(true)
    generateQuestion(item.id)
      .then((updated) => {
        if (!cancelled) setItem(updated)
      })
      .catch((cause: unknown) => {
        // A missing question is not a broken card — the reflection is still
        // answerable, so surface the failure and let the user write anyway.
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : String(cause))
        }
      })
      .finally(() => {
        if (!cancelled) setGenerating(false)
      })
    return () => {
      cancelled = true
    }
  }, [needsQuestion, item.id])

  const handleSave = useCallback(async () => {
    if (saving || !response.trim()) return
    setSaving(true)
    setError(null)
    try {
      setItem(await answerPostMortem(item.id, response.trim()))
      onChanged?.()
    } catch (cause: unknown) {
      // The typed response stays in the textarea — nothing written is lost.
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setSaving(false)
    }
  }, [saving, response, item.id, onChanged])

  if (dismissed) return null

  const question = manual ? MANUAL_QUESTION : item.prompt_question
  const answered = item.user_response !== null

  return (
    <Card className="relative border border-border transition-colors [--card-spacing:--spacing(6)] hover:border-border-strong">
      {/* The status the thesis was in when it broke — the reflection is about
          that moment, and the thesis has kept moving since. */}
      <StatusSpine status={item.status_at_break} />
      <div className="flex flex-col gap-4 px-(--card-spacing)">
        <header className="flex flex-wrap items-center gap-2">
          <CompanyLogo ticker={item.ticker} logoUrl={item.logo_url} size={24} />
          <span className="font-display text-base tracking-[0.01em] text-text-primary">
            {item.ticker}
          </span>
          <StatusBadge status={item.status_at_break} />
          <span className="ml-auto text-xs text-text-muted">
            {formatRelative(answered ? item.answered_at! : item.created_at)}
          </span>
        </header>

        {item.broken_claim_statement && (
          <div>
            <p className="text-xs tracking-wide text-text-muted uppercase">
              Claim that broke
            </p>
            {/* Serif: the claim is prose, same family as the question below. */}
            <p className="mt-1 font-serif text-[15px] leading-[1.5] text-text-secondary">
              {item.broken_claim_statement}
            </p>
          </div>
        )}

        {generating ? (
          <p className="flex items-center gap-2 text-sm text-text-secondary">
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
            Preparing your question…
          </p>
        ) : question ? (
          <p className="font-serif text-[16px] leading-[1.5] text-text-primary">
            {question}
          </p>
        ) : null}

        {answered ? (
          <AnsweredBody item={item} onDeleted={onChanged} />
        ) : (
          <div className="flex flex-col gap-3">
            <Textarea
              value={response}
              onChange={(event) => setResponse(event.target.value)}
              placeholder="What were you thinking at the time?"
              disabled={saving}
              className="min-h-32 font-serif text-[15px] leading-relaxed"
            />

            {error && (
              <p role="alert" className="text-sm text-status-broken">
                {error}
              </p>
            )}

            <div className="flex items-center gap-2">
              <Button onClick={handleSave} disabled={saving || !response.trim()}>
                {saving && <Loader2 className="animate-spin" aria-hidden />}
                {saving ? 'Saving…' : 'Save'}
              </Button>
              {/* Reflection is NEVER blocking: skipping hides the card for this
                  session and changes nothing on the server, so it comes back. */}
              <Button
                variant="ghost"
                onClick={() => setDismissed(true)}
                className="text-text-secondary"
              >
                Skip for now
              </Button>
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}

function AnsweredBody({
  item,
  onDeleted,
}: {
  item: PostMortem
  onDeleted?: () => void
}) {
  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [gone, setGone] = useState(false)

  async function handleDelete() {
    if (deleting) return
    setDeleting(true)
    setError(null)
    try {
      await deletePostMortem(item.id)
      setGone(true)
      onDeleted?.()
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : String(cause))
      setDeleting(false)
    }
  }

  if (gone) return null

  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="text-xs tracking-wide text-text-muted uppercase">Your answer</p>
        <p className="mt-1 font-serif text-[15px] leading-relaxed whitespace-pre-wrap text-text-secondary">
          {item.user_response}
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm text-status-broken">
          {error}
        </p>
      )}

      {/* Inline two-step confirm rather than window.confirm — this is a deletion the
          user cannot undo, so it asks, but without a modal interrupting the page. */}
      {confirming ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-text-secondary">Delete this reflection?</span>
          <Button variant="destructive" size="sm" onClick={handleDelete} disabled={deleting}>
            {deleting && <Loader2 className="animate-spin" aria-hidden />}
            Delete
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setConfirming(false)}
            disabled={deleting}
            className="text-text-secondary"
          >
            Cancel
          </Button>
        </div>
      ) : (
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setConfirming(true)}
            className="text-text-muted hover:text-text-primary"
          >
            <Trash2 aria-hidden />
            Delete
          </Button>
        </div>
      )}
    </div>
  )
}
