import { useRef, useState, type FormEvent } from 'react'
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { submitDocument } from '@/lib/api'

type Outcome =
  | { kind: 'created'; count: number; stale: boolean }
  | { kind: 'nothing-relevant'; stale: boolean }
  | { kind: 'error'; message: string }

export function AddDocumentPanel({
  thesisId,
  onSubmitted,
}: {
  thesisId: string
  /** Revalidates the thesis so claim statuses reflect the new evidence. */
  onSubmitted: () => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [pending, setPending] = useState(false)
  const [outcome, setOutcome] = useState<Outcome | null>(null)

  // A ref, not `pending`, so a second submit in the same tick still bounces.
  const inFlight = useRef(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (inFlight.current || !text.trim()) return

    inFlight.current = true
    setPending(true)
    setOutcome(null)

    try {
      const events = await submitDocument(
        thesisId,
        text.trim(),
        title.trim() || undefined,
      )

      // Refetch on every success, including the zero-event case — the document
      // was stored either way, so the page should never show a pre-submit view.
      // A refetch failure isn't a failed submission, so it rides along on the
      // success outcome rather than replacing it.
      let stale = false
      try {
        await onSubmitted()
      } catch {
        stale = true
      }

      setOutcome(
        events.length === 0
          ? // Not a failure: the document simply didn't bear on any claim.
            { kind: 'nothing-relevant', stale }
          : { kind: 'created', count: events.length, stale },
      )
      setText('')
      setTitle('')
    } catch (cause: unknown) {
      // Pasted text is deliberately left intact so nothing is lost.
      setOutcome({
        kind: 'error',
        message: cause instanceof Error ? cause.message : String(cause),
      })
    } finally {
      inFlight.current = false
      setPending(false)
    }
  }

  return (
    <Card className="[--card-spacing:--spacing(5)]">
      <div className="px-(--card-spacing)">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex w-full items-center gap-2 rounded-lg text-left text-sm font-medium text-text-primary focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {open ? (
            <ChevronDown className="size-4 text-text-muted" aria-hidden />
          ) : (
            <ChevronRight className="size-4 text-text-muted" aria-hidden />
          )}
          Add document
          <span className="font-normal text-text-muted">
            — paste an earnings call, filing, or note
          </span>
        </button>
      </div>

      {open && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-(--card-spacing)">
          <fieldset disabled={pending} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <label htmlFor="doc-title" className="text-sm text-text-secondary">
                Title <span className="text-text-muted">(optional)</span>
              </label>
              <Input
                id="doc-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Q3 FY26 earnings call"
                autoComplete="off"
                className="max-w-md"
              />
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="doc-text" className="text-sm text-text-secondary">
                Document text
              </label>
              <Textarea
                id="doc-text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste the full text here…"
                className="min-h-64 leading-relaxed"
              />
            </div>
          </fieldset>

          {pending ? (
            <div className="flex items-start gap-3 rounded-lg bg-surface-raised px-4 py-3">
              <Loader2
                className="mt-0.5 size-4 shrink-0 animate-spin text-text-muted"
                aria-hidden
              />
              <div>
                <p className="text-sm text-text-primary">Verifying against claims…</p>
                <p className="mt-1 text-sm text-text-secondary">
                  Every claim gets its own read of this document, so this usually takes
                  10–40 seconds. Leave the page open.
                </p>
              </div>
            </div>
          ) : (
            outcome && <OutcomeMessage outcome={outcome} />
          )}

          <div>
            <Button type="submit" disabled={pending || !text.trim()}>
              {pending && <Loader2 className="animate-spin" aria-hidden />}
              {pending ? 'Verifying against claims…' : 'Verify document'}
            </Button>
          </div>
        </form>
      )}
    </Card>
  )
}

function OutcomeMessage({ outcome }: { outcome: Outcome }) {
  if (outcome.kind === 'error') {
    return (
      <div role="alert">
        <p className="text-sm font-medium text-text-primary">
          Couldn't verify the document
        </p>
        <p className="mt-1 text-sm text-status-broken">{outcome.message}</p>
      </div>
    )
  }

  return (
    <div role="status">
      {outcome.kind === 'nothing-relevant' ? (
        // Deliberately neutral: finding nothing relevant is a real, valid answer.
        <p className="text-sm text-text-secondary">
          Checked — nothing in this document relates to your claims.
        </p>
      ) : (
        <p className="text-sm text-status-supported">
          {outcome.count} new evidence {outcome.count === 1 ? 'event' : 'events'}. Claim
          statuses below have been updated.
        </p>
      )}
      {outcome.stale && (
        <p className="mt-1 text-sm text-status-weakening">
          Reloading the thesis failed, so what's shown below may be out of date.
        </p>
      )}
    </div>
  )
}
