import { useState, type FormEvent } from 'react'
import { ChevronDown, ChevronRight, Loader2, Plus } from 'lucide-react'

import { Field } from '@/components/portfolio/HoldingsTable'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { createHolding, type Portfolio } from '@/lib/api'

/**
 * Collapsed by default, like AddDocumentPanel: the portfolio is for reading most of
 * the time, and a permanently open form would push the table down the page.
 */
export function AddHoldingForm({ onAdded }: { onAdded: (portfolio: Portfolio) => void }) {
  const [open, setOpen] = useState(false)
  const [ticker, setTicker] = useState('')
  const [shares, setShares] = useState('')
  const [averageCost, setAverageCost] = useState('')
  const [purchasedAt, setPurchasedAt] = useState('')
  const [note, setNote] = useState('')
  const [problem, setProblem] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  /**
   * Mirrors backend/api/schemas.py:HoldingCreateRequest exactly — shares > 0,
   * average_cost >= 0, ticker non-empty. Kept in step deliberately: an inline rule
   * stricter or looser than the server's would either block a valid entry or
   * promise one that comes back a 422.
   */
  function validate(): string | null {
    if (!ticker.trim()) return 'Enter a ticker.'
    const sharesValue = Number(shares)
    if (!shares.trim() || !Number.isFinite(sharesValue) || sharesValue <= 0) {
      return 'Shares must be greater than 0.'
    }
    const costValue = Number(averageCost)
    if (!averageCost.trim() || !Number.isFinite(costValue) || costValue < 0) {
      return 'Average cost cannot be negative.'
    }
    return null
  }

  function reset() {
    setTicker('')
    setShares('')
    setAverageCost('')
    setPurchasedAt('')
    setNote('')
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return

    const found = validate()
    setProblem(found)
    if (found) return

    setPending(true)
    try {
      // The POST answers with the WHOLE portfolio, because a new position changes
      // every existing row's allocation percentage.
      const portfolio = await createHolding({
        ticker: ticker.trim(), // the backend uppercases it
        shares: Number(shares),
        average_cost: Number(averageCost),
        purchased_at: purchasedAt || null,
        note: note.trim() || null,
      })
      onAdded(portfolio)
      reset()
      setOpen(false)
    } catch (cause: unknown) {
      // Values are left intact so nothing typed is lost.
      setProblem(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setPending(false)
    }
  }

  return (
    <Card className="mb-8 [--card-spacing:--spacing(5)]">
      <div className="px-(--card-spacing)">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="flex w-full items-center gap-2 rounded-lg text-left text-sm focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {open ? (
            <ChevronDown className="size-4 shrink-0 text-text-muted" aria-hidden />
          ) : (
            <ChevronRight className="size-4 shrink-0 text-text-muted" aria-hidden />
          )}
          <span className="font-medium text-text-primary">Add holding</span>
          <span className="text-text-muted">— what you own, and what you paid</span>
        </button>

        {open && (
          <form
            onSubmit={handleSubmit}
            // noValidate because `min="0"` below otherwise makes the BROWSER reject
            // a negative cost with its own popup, before onSubmit ever runs — so the
            // inline message never appeared, while a zero share count (which `min`
            // permits but our rule doesn't) did get one. Two adjacent fields, two
            // different error styles. validate() now owns every case; the `min`
            // attributes stay purely as spinner/keypad hints.
            noValidate
            className="mt-4 flex flex-wrap items-end gap-3"
          >
            <Field label="Ticker" htmlFor="add-ticker">
              <Input
                id="add-ticker"
                value={ticker}
                onChange={(event) => setTicker(event.target.value)}
                placeholder="NVDA"
                autoComplete="off"
                spellCheck={false}
                className="w-28 font-mono uppercase"
              />
            </Field>
            <Field label="Shares" htmlFor="add-shares">
              <Input
                id="add-shares"
                type="number"
                step="any"
                min="0"
                value={shares}
                onChange={(event) => setShares(event.target.value)}
                placeholder="10"
                className="w-28 font-mono tabular-nums"
              />
            </Field>
            <Field label="Average cost" htmlFor="add-cost">
              <Input
                id="add-cost"
                type="number"
                step="any"
                min="0"
                value={averageCost}
                onChange={(event) => setAverageCost(event.target.value)}
                placeholder="100.00"
                className="w-32 font-mono tabular-nums"
              />
            </Field>
            <Field label="Purchased (optional)" htmlFor="add-date">
              <Input
                id="add-date"
                type="date"
                value={purchasedAt}
                onChange={(event) => setPurchasedAt(event.target.value)}
                className="w-40 font-mono"
              />
            </Field>
            <Field label="Note (optional)" htmlFor="add-note" className="min-w-48 flex-1">
              <Input
                id="add-note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Why you bought it"
              />
            </Field>

            <Button type="submit" disabled={pending}>
              {pending ? <Loader2 className="animate-spin" aria-hidden /> : <Plus aria-hidden />}
              Add
            </Button>

            {problem && (
              <p role="alert" className="w-full text-sm text-status-broken">
                {problem}
              </p>
            )}
          </form>
        )}
      </div>
    </Card>
  )
}
