import { useState, type FormEvent, type ReactNode } from 'react'
import { Loader2, Pencil, Trash2 } from 'lucide-react'
import { Link } from 'react-router'

import { CompanyLogo } from '@/components/CompanyLogo'
import { Sparkline } from '@/components/Sparkline'
import { StatusBadge } from '@/components/StatusBadge'
import { spineBorderStyle } from '@/components/StatusSpine'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useToast } from '@/components/ui/toast'
import { Tooltip } from '@/components/ui/tooltip'
import { useStaggerIndex } from '@/hooks/useStaggerIndex'
import {
  deleteHolding,
  updateHolding,
  type Holding,
  type Portfolio,
} from '@/lib/api'
import {
  UNAVAILABLE,
  formatPlainDate,
  formatMoney,
  formatPercent,
  formatShares,
  formatSignedMoney,
  formatSignedPercent,
  signOf,
} from '@/lib/format'
import { entryProps } from '@/lib/motion'
import { cn } from '@/lib/utils'

/** Right-aligned, mono, tabular — so digits line up column-wise for scanning. */
const NUM = 'px-3 py-3 text-right font-mono text-sm tabular-nums whitespace-nowrap'
const HEAD =
  'px-3 py-2 text-right font-mono text-[11px] tracking-[0.08em] text-text-muted uppercase whitespace-nowrap'

export function HoldingsTable({
  holdings,
  onPortfolio,
  onRefetch,
}: {
  holdings: Holding[]
  /** Swap in the portfolio a mutation returned — every row's allocation changed. */
  onPortfolio: (portfolio: Portfolio) => void
  /** For DELETE, which answers 204 and so carries no new portfolio. */
  onRefetch: () => Promise<void>
}) {
  const staggerIndex = useStaggerIndex(holdings.length > 0)

  return (
    // The table is wide by nature; it scrolls inside its own box rather than
    // pushing the page sideways.
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full border-collapse">
        <caption className="sr-only">
          Your holdings, with size, cost, current value and the status of any thesis
          you have written on the same ticker.
        </caption>
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className={cn(HEAD, 'text-left')}>
              Holding
            </th>
            <th scope="col" className={cn(HEAD, 'text-left')}>
              Thesis
            </th>
            <th scope="col" className={HEAD}>
              Shares
            </th>
            <th scope="col" className={HEAD}>
              Avg cost
            </th>
            <th scope="col" className={HEAD}>
              Price
            </th>
            {/* Beside Price, because it is the same fact over time. */}
            <th scope="col" className={cn(HEAD, 'text-left')}>
              30d
            </th>
            <th scope="col" className={HEAD}>
              Value
            </th>
            <th scope="col" className={HEAD}>
              P&L
            </th>
            <th scope="col" className={HEAD}>
              Alloc
            </th>
            <th scope="col" className={cn(HEAD, 'text-right')}>
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {/* Re-sorting MOVES these rows. A move is a DOM remove-and-reinsert,
              which restarts a CSS animation — see useStaggerIndex, which is what
              stops a re-sort from replaying every row's entrance. */}
          {holdings.map((holding, index) => (
            <HoldingRow
              key={holding.id}
              holding={holding}
              index={staggerIndex(index)}
              onPortfolio={onPortfolio}
              onRefetch={onRefetch}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function HoldingRow({
  holding,
  index,
  onPortfolio,
  onRefetch,
}: {
  holding: Holding
  /** Position in the staggered entry. */
  index?: number
  onPortfolio: (portfolio: Portfolio) => void
  onRefetch: () => Promise<void>
}) {
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [busy, setBusy] = useState(false)
  // Stays INLINE, under the row it belongs to: a delete that failed leaves the
  // row on screen, and which row failed is half the message.
  const [error, setError] = useState<string | null>(null)

  const tone = signOf(holding.unrealised_pnl)
  // One reason, shared by every dash in the row — they all have the same cause.
  const reason = unavailableReason(holding)

  async function handleDelete() {
    setBusy(true)
    setError(null)
    try {
      await deleteHolding(holding.id)
      // A refetch, not a local splice: removing a position changes every other
      // row's allocation percentage.
      await onRefetch()
      // The row is gone by now, so the confirmation cannot live in it.
      toast.success(`${holding.ticker} removed from your portfolio`)
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : String(cause))
      setBusy(false)
      setConfirmingDelete(false)
    }
  }

  return (
    <>
      {/* Only the data row animates. The error and edit rows below open in
          response to a click and would be a second, unrelated entrance. */}
      <tr
        {...entryProps(
          index,
          'border-b border-border/60 last:border-b-0 hover:bg-surface-raised/40',
        )}
      >
        {/* Holding. The left border is the status spine — same colour map as the
            cards, transparent when this holding has no thesis so the column
            stays aligned. */}
        <td className="px-3 py-3" style={spineBorderStyle(holding.thesis_status)}>
          <div className="flex items-center gap-2.5">
            <CompanyLogo ticker={holding.ticker} logoUrl={holding.logo_url} size={28} />
            <div className="min-w-0">
              <Link
                to={`/research/${encodeURIComponent(holding.ticker)}`}
                className="rounded font-mono text-sm text-text-primary underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                {holding.ticker}
              </Link>
              {holding.price_unavailable && <PriceProblem holding={holding} />}
              {holding.purchased_at && !holding.price_unavailable && (
                <div className="text-xs text-text-muted">
                  Bought {formatPlainDate(holding.purchased_at)}
                </div>
              )}
            </div>
          </div>
          {holding.note && (
            <p className="mt-1.5 max-w-[22ch] font-serif text-xs leading-snug text-text-secondary">
              {holding.note}
            </p>
          )}
        </td>

        {/* ⭐ The connection between what you own and what you believe. */}
        <td className="px-3 py-3">
          <ThesisCell holding={holding} />
        </td>

        <td className={cn(NUM, 'text-text-secondary')}>{formatShares(holding.shares)}</td>
        <td className={cn(NUM, 'text-text-secondary')}>
          {formatMoney(holding.average_cost)}
        </td>

        {/* Every cell below is null — never 0 — when the price could not be
            fetched, and each dash carries the reason on hover. */}
        <td className={cn(NUM, 'text-text-secondary')}>
          <OrUnavailable
            value={holding.current_price}
            render={formatMoney}
            reason={reason}
          />
        </td>
        {/* Renders nothing at all for an unpriced ticker, but keeps its box, so
            the column stays aligned down the table. */}
        <td className="px-3 py-3">
          <Sparkline ticker={holding.ticker} days={30} />
        </td>
        <td className={cn(NUM, 'text-text-primary')}>
          <OrUnavailable
            value={holding.market_value}
            render={formatMoney}
            reason={reason}
          />
        </td>
        <td
          className={cn(
            NUM,
            tone === 'positive'
              ? 'text-status-strengthening'
              : tone === 'negative'
                ? 'text-status-broken'
                : 'text-text-secondary',
          )}
        >
          {holding.unrealised_pnl === null ? (
            <Unavailable reason={reason} />
          ) : (
            <>
              <div>{formatSignedMoney(holding.unrealised_pnl)}</div>
              <div className="text-xs opacity-80">
                {formatSignedPercent(holding.pnl_percent)}
              </div>
            </>
          )}
        </td>
        <td className={cn(NUM, 'text-text-secondary')}>
          <OrUnavailable
            value={holding.allocation_percent}
            render={formatPercent}
            reason={reason}
          />
        </td>

        <td className="px-3 py-3 text-right whitespace-nowrap">
          {confirmingDelete ? (
            // Inline two-step rather than a browser confirm(): it keeps the row in
            // view, so it is clear WHICH holding is about to go.
            <span className="inline-flex items-center gap-1.5">
              <span className="text-xs text-text-secondary">Delete?</span>
              <Button
                size="xs"
                variant="destructive"
                onClick={handleDelete}
                disabled={busy}
              >
                {busy ? <Loader2 className="animate-spin" aria-hidden /> : null}
                Delete
              </Button>
              <Button
                size="xs"
                variant="ghost"
                onClick={() => setConfirmingDelete(false)}
                disabled={busy}
              >
                Cancel
              </Button>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1">
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label={`Edit ${holding.ticker}`}
                aria-expanded={editing}
                onClick={() => setEditing((open) => !open)}
              >
                <Pencil />
              </Button>
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label={`Delete ${holding.ticker}`}
                onClick={() => setConfirmingDelete(true)}
              >
                <Trash2 />
              </Button>
            </span>
          )}
        </td>
      </tr>

      {error && (
        <tr>
          <td colSpan={10} className="px-3 pb-3 text-sm text-status-broken">
            {error}
          </td>
        </tr>
      )}

      {editing && (
        <tr className="border-b border-border/60 bg-surface-raised/30">
          <td colSpan={10} className="px-3 py-4">
            <EditHoldingForm
              holding={holding}
              onCancel={() => setEditing(false)}
              onSaved={(portfolio) => {
                onPortfolio(portfolio)
                setEditing(false)
                // Same reason as the delete: the edit form closes on success, so
                // the confirmation has nowhere on the row left to live.
                toast.success(`${holding.ticker} updated`)
              }}
            />
          </td>
        </tr>
      )}
    </>
  )
}

/**
 * Why a cell has no number, in the reader's terms.
 *
 * ⚠️ Branches on `price_status` from the backend, never on the wording of
 * `price_error` — same rule as PriceProblem below. The backend's own message is
 * appended when there is one, because for a network failure it is the only thing
 * that says WHAT failed.
 */
function unavailableReason(holding: Holding): string {
  if (holding.price_status === 'unknown_ticker') {
    return `No price source recognises ${holding.ticker}, so nothing here can be valued. Check the symbol.`
  }
  if (holding.price_unavailable) {
    return holding.price_error
      ? `The price source could not be reached, so this could not be valued: ${holding.price_error}`
      : 'The price source could not be reached, so this could not be valued.'
  }
  // The row priced fine and a single figure is still missing — a zero cost basis
  // leaves P&L with no percentage to be one of.
  return 'There is no figure to show here — not a value of zero.'
}

/**
 * The em dash for an unavailable number, with the reason spelled out for screen
 * readers. Never "0", and never a hyphen — beside a column of figures a hyphen
 * reads as a minus sign.
 *
 * ⚠️ THE DASH NOW SAYS WHY. The em dash is honest about there being no number
 * but silent about the cause, and "my position shows no value" is precisely the
 * moment a reader needs to know whether the ticker is wrong or the price feed is
 * down — one is theirs to fix, the other is not. `cursor-help` marks it as
 * having something to say, since a dash gives no other hint.
 */
function Unavailable({ reason }: { reason?: string }) {
  const dash = (
    <span className={cn('text-text-muted', reason && 'cursor-help')}>
      <span aria-hidden>{UNAVAILABLE}</span>
      {/* The reason is in the accessible name too, not only the tooltip: Radix
          hides tooltip content from screen readers by design. */}
      <span className="sr-only">unavailable{reason ? `. ${reason}` : ''}</span>
    </span>
  )

  return reason ? <Tooltip content={reason}>{dash}</Tooltip> : dash
}

function OrUnavailable({
  value,
  render,
  reason,
}: {
  value: number | null
  render: (value: number) => string
  reason?: string
}) {
  return value === null ? <Unavailable reason={reason} /> : <>{render(value)}</>
}

/**
 * Which of the two price failures this is. Branches on `price_status` from the
 * backend, not on the wording of `price_error` — the message is for humans and is
 * free to change.
 */
function PriceProblem({ holding }: { holding: Holding }) {
  const unknownTicker = holding.price_status === 'unknown_ticker'
  return (
    <div
      className="text-xs text-text-secondary"
      // The backend's own wording, on hover, for when the short label isn't enough.
      title={holding.price_error ?? undefined}
    >
      {unknownTicker ? 'Ticker not recognised' : 'Price source unreachable'}
    </div>
  )
}

/**
 * The link between a position and the thinking behind it — or the absence of one.
 *
 * With no thesis this is an INVITATION, not a nag: a quiet line in muted text, the
 * same weight as any other secondary detail. Nothing is coloured, counted or
 * badged to imply the user has left something undone. Owning a stock you have not
 * written up is a normal state, not an incomplete one.
 */
function ThesisCell({ holding }: { holding: Holding }) {
  if (holding.thesis_id && holding.thesis_status) {
    return (
      <Link
        to={`/theses/${holding.thesis_id}`}
        className="inline-flex rounded-[4px] focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <StatusBadge status={holding.thesis_status} />
      </Link>
    )
  }

  return (
    <Link
      to={`/theses/new?ticker=${encodeURIComponent(holding.ticker)}`}
      className="rounded-lg text-xs text-text-muted underline-offset-4 transition-colors hover:text-text-secondary hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      No thesis
    </Link>
  )
}

function EditHoldingForm({
  holding,
  onSaved,
  onCancel,
}: {
  holding: Holding
  onSaved: (portfolio: Portfolio) => void
  onCancel: () => void
}) {
  const [shares, setShares] = useState(String(holding.shares))
  const [averageCost, setAverageCost] = useState(String(holding.average_cost))
  const [note, setNote] = useState(holding.note ?? '')
  const [problem, setProblem] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return

    // Mirrors the backend's constraints exactly, so the inline message and the 422
    // can never disagree about what is allowed.
    const sharesValue = Number(shares)
    const costValue = Number(averageCost)
    if (!Number.isFinite(sharesValue) || sharesValue <= 0) {
      setProblem('Shares must be greater than 0.')
      return
    }
    if (!Number.isFinite(costValue) || costValue < 0) {
      setProblem('Average cost cannot be negative.')
      return
    }

    setProblem(null)
    setPending(true)
    try {
      const trimmed = note.trim()
      const portfolio = await updateHolding(holding.id, {
        shares: sharesValue,
        average_cost: costValue,
        // Explicit null CLEARS the note; the key is always sent because this form
        // shows the field, so an emptied box means the user meant to empty it.
        note: trimmed === '' ? null : trimmed,
      })
      onSaved(portfolio)
    } catch (cause: unknown) {
      setProblem(cause instanceof Error ? cause.message : String(cause))
      setPending(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      // See the note in AddHoldingForm: `min="0"` would otherwise let the browser
      // block submission with its own popup and bypass these inline messages.
      noValidate
      className="flex flex-wrap items-end gap-3"
    >
      <Field label="Shares" htmlFor={`shares-${holding.id}`}>
        <Input
          id={`shares-${holding.id}`}
          type="number"
          step="any"
          min="0"
          value={shares}
          onChange={(event) => setShares(event.target.value)}
          className="w-28 font-mono tabular-nums"
        />
      </Field>
      <Field label="Average cost" htmlFor={`cost-${holding.id}`}>
        <Input
          id={`cost-${holding.id}`}
          type="number"
          step="any"
          min="0"
          value={averageCost}
          onChange={(event) => setAverageCost(event.target.value)}
          className="w-32 font-mono tabular-nums"
        />
      </Field>
      <Field label="Note" htmlFor={`note-${holding.id}`} className="min-w-48 flex-1">
        <Input
          id={`note-${holding.id}`}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Optional"
        />
      </Field>

      <div className="flex items-center gap-2">
        <Button type="submit" size="sm" disabled={pending}>
          {pending && <Loader2 className="animate-spin" aria-hidden />}
          Save
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel} disabled={pending}>
          Cancel
        </Button>
      </div>

      {problem && (
        <p role="alert" className="w-full text-sm text-status-broken">
          {problem}
        </p>
      )}
    </form>
  )
}

export function Field({
  label,
  htmlFor,
  className,
  children,
}: {
  label: string
  htmlFor: string
  className?: string
  children: ReactNode
}) {
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <label
        htmlFor={htmlFor}
        className="font-mono text-[11px] tracking-[0.08em] text-text-muted uppercase"
      >
        {label}
      </label>
      {children}
    </div>
  )
}
