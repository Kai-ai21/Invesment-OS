import { useState, type FormEvent } from 'react'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Link, useNavigate } from 'react-router'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { createThesis } from '@/lib/api'

const MIN_REASONING_LENGTH = 20

const REASONING_PLACEHOLDER = `Nvidia's data-centre revenue keeps compounding because hyperscaler capex is still rising and CUDA keeps switching costs high. I expect data-centre revenue to grow at least 40% year over year for the next four quarters, and gross margin to hold above 70%.

The thesis breaks if a major hyperscaler moves meaningful inference volume to in-house silicon, or if gross margin falls below 65% for two consecutive quarters.`

export function NewThesisPage() {
  const navigate = useNavigate()

  const [ticker, setTicker] = useState('')
  const [reasoning, setReasoning] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)

  function validate(): string | null {
    if (!ticker.trim()) return 'Enter a ticker.'
    if (!reasoning.trim()) return 'Enter your reasoning.'
    if (reasoning.trim().length < MIN_REASONING_LENGTH) {
      return `Reasoning needs at least ${MIN_REASONING_LENGTH} characters — give the extractor something to work with.`
    }
    return null
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return // guards Enter-key resubmits while the request is in flight

    const problem = validate()
    setValidationError(problem)
    if (problem) return

    setError(null)
    setPending(true)
    try {
      const thesis = await createThesis(ticker.trim(), reasoning.trim())
      navigate(`/theses/${thesis.id}`)
    } catch (cause: unknown) {
      // Form values are deliberately left intact so nothing typed is lost.
      setError(cause instanceof Error ? cause.message : String(cause))
      setPending(false)
    }
  }

  return (
    <div>
      <Link
        to="/theses"
        className="inline-flex items-center gap-1.5 rounded-lg text-sm text-text-secondary transition-colors hover:text-text-primary focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <ArrowLeft className="size-4" aria-hidden />
        All theses
      </Link>

      <header className="mt-6 mb-8">
        <h1 className="font-heading text-2xl font-medium text-text-primary">
          New thesis
        </h1>
        <p className="mt-2 text-sm text-text-secondary">
          Write out your reasoning in plain language. We'll extract the individual
          claims, each with a proof and a break condition, and track them from there.
        </p>
      </header>

      <Card className="[--card-spacing:--spacing(6)]">
        <form onSubmit={handleSubmit} className="flex flex-col gap-6 px-(--card-spacing)">
          <fieldset disabled={pending} className="flex flex-col gap-6">
            <div className="flex flex-col gap-2">
              <label htmlFor="ticker" className="text-sm font-medium text-text-primary">
                Ticker
              </label>
              <Input
                id="ticker"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="NVDA"
                autoComplete="off"
                autoCapitalize="characters"
                spellCheck={false}
                maxLength={10}
                className="w-32 font-heading tracking-wide"
              />
            </div>

            <div className="flex flex-col gap-2">
              <label
                htmlFor="reasoning"
                className="text-sm font-medium text-text-primary"
              >
                Reasoning
              </label>
              <Textarea
                id="reasoning"
                value={reasoning}
                onChange={(e) => setReasoning(e.target.value)}
                placeholder={REASONING_PLACEHOLDER}
                className="min-h-72 leading-relaxed"
              />
              <p className="text-xs text-text-muted">
                At least {MIN_REASONING_LENGTH} characters. Say what has to be true for
                you to be right — and what would prove you wrong.
              </p>
            </div>
          </fieldset>

          {validationError && (
            <p className="text-sm text-status-weakening" role="alert">
              {validationError}
            </p>
          )}

          {error && (
            <div role="alert" className="flex flex-col gap-1">
              <p className="text-sm font-medium text-text-primary">
                Couldn't create the thesis
              </p>
              <p className="text-sm text-status-broken">{error}</p>
            </div>
          )}

          <div className="flex items-center gap-3">
            <Button type="submit" disabled={pending}>
              {pending && <Loader2 className="animate-spin" aria-hidden />}
              {pending ? 'Extracting claims…' : 'Create thesis'}
            </Button>
            {pending && (
              <span className="text-sm text-text-muted">
                This usually takes 5–15 seconds.
              </span>
            )}
          </div>
        </form>
      </Card>
    </div>
  )
}
