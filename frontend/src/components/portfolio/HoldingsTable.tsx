import { useState, type FormEvent, type ReactNode } from 'react'
import { Loader2, Pencil, Trash2 } from 'lucide-react'
import { Link } from 'react-router'

import { CompanyLogo } from '@/components/CompanyLogo'
import { Sparkline } from '@/components/Sparkline'
import { StatusBadge } from '@/components/StatusBadge'
import { StatusGlow } from '@/components/StatusSurface'
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
import { describeError } from '@/lib/errors'
import { entryProps } from '@/lib/motion'
import { cn } from '@/lib/utils'

/** Right-aligned, mono, tabular — so digits line up column-wise for scanning.
 *
 * ⚠️ BELOW md THE SAME CELL IS A LABELLED ROW INSIDE A CARD. The column heading
 * it used to sit under is hidden, so the cell grows its own label from
 * `data-label` via ::before — which is why every numeric <td> must carry that
 * attribute. Without it the figure appears with nothing saying what it is.
 * The figure stays right-aligned, so a column of them still lines up down the
 * card exactly as it did across the table. */
const NUM =
  'px-3 py-3 text-right font-mono text-sm tabular-nums whitespace-nowrap ' +
  'max-xl:flex max-xl:items-baseline max-xl:justify-between max-xl:gap-4 max-xl:px-0 max-xl:py-1 ' +
  "max-xl:before:content-[attr(data-label)] max-xl:before:font-mono max-xl:before:normal-case " +
  'max-xl:before:text-[length:var(--text-2xs)] max-xl:before:tracking-[0.08em] max-xl:before:text-text-muted'
const HEAD =
  'px-3 py-2 text-right font-mono text-2xs tracking-[0.08em] text-text-muted uppercase whitespace-nowrap'

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
    /* ⚠️ THE INSET SHELL GOES ON THE TABLE, NOT ON EACH ROW, and that is the
       only honest way to apply it here. The rows are contiguous — they share
       hairlines and have no gap at all — so a ring per row would have nothing to
       stand in and every ring would collide with its neighbours'. The status
       still reads per row: each one blooms from the top-left of its leading
       cell. So the portfolio's status-bearing surface is the table, and it gets
       the same face, the same hairline and the same outer ring as a thesis card.

       No hover on this one: the whole table is not a target, and brightening its
       frame because the cursor crossed a cell would be noise. Row hover is
       unchanged and still lands on the row. */
    /* ⚠️ BELOW md THIS IS NOT A TABLE AT ALL — every row becomes its own card,
       and the whole conversion is CSS. The markup below is untouched: one DOM
       tree, one set of handlers, one edit form. The alternative (a second
       card component beside the table) would have duplicated 300 lines of
       delete-confirm and edit state, and the two would have drifted.

       Every class added for narrow widths is prefixed `max-xl:`, so nothing here
       can reach the desktop layout even by accident — which is what makes the
       1280px fingerprint match by construction.

       The shell and the scroller are md-and-up only: at phone width the cards
       carry their own borders, and there is nothing left to scroll sideways. */
    <div
      className={cn(
        'bg-surface-inset max-xl:bg-transparent',
        // ⚠️ SPELLED OUT, NOT BUILT FROM INSET_SURFACE AT RUNTIME. Tailwind
        // generates CSS by scanning the source for literal class strings, so a
        // name assembled with string concatenation produces no rule at all — the
        // markup would carry classes that style nothing. These are INSET_SURFACE's
        // own utilities, md-prefixed by hand for exactly that reason.
        'xl:overflow-x-auto xl:rounded-xl xl:border xl:border-border xl:ring-0 xl:outline-1 xl:outline-offset-2 xl:outline-card-ring',
      )}
    >
      <table className="w-full border-collapse max-xl:block">
        <caption className="sr-only">
          Your holdings, with size, cost, current value and the status of any thesis
          you have written on the same ticker.
        </caption>
        {/* Hidden, not removed: the column names still label the cells below via
            data-label, and a screen reader still gets a real table on desktop. */}
        <thead className="max-xl:hidden">
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
        <tbody className="max-xl:block max-xl:space-y-3">
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
      setError(describeError(cause, 'this holding').detail)
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
          // The desktop half is unchanged. Below md the row IS the card: its own
          // fill, border and ring — the shell the wrapper stops drawing at that
          // width — and no bottom hairline, because cards are separated by the
          // gap on <tbody> instead.
          'group/glow border-b border-border/60 last:border-b-0 hover:bg-surface-raised/40 ' +
            'max-xl:block max-xl:rounded-xl max-xl:border max-xl:border-border max-xl:bg-surface-inset ' +
            'max-xl:p-4 max-xl:outline-1 max-xl:outline-offset-2 max-xl:outline-card-ring',
        )}
      >
        {/* Holding, and the cell the status blooms out of — same colour map and
            same component as the cards.

            ⚠️ THE ONLY PLACE GLOW_HOST IS SPLIT ACROSS TWO ELEMENTS, and both
            halves are forced. `relative isolate` has to be on the CELL: a <tr>
            is not a reliable positioning context — an absolutely positioned
            child of one resolves against the table or the page rather than the
            row — while a <td> positions its children like any other box.
            `group/glow` has to be on the ROW: hovering the P&L column should
            light the corner, the same as the row's own background hover, and a
            group scoped to this cell would only fire over the ticker. */}
        <td className="relative isolate px-3 py-3 max-xl:block max-xl:px-0 max-xl:pt-0 max-xl:pb-2">
          <StatusGlow status={holding.thesis_status} />
          <div className="flex items-center gap-2.5">
            <CompanyLogo ticker={holding.ticker} logoUrl={holding.logo_url} size={28} />
            <div className="min-w-0">
              <Link
                to={`/research/${encodeURIComponent(holding.ticker)}`}
                className="rounded-lg font-mono text-sm text-text-primary underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
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
        <td
          data-label="Thesis"
          className="px-3 py-3 max-xl:flex max-xl:items-baseline max-xl:justify-between max-xl:gap-4 max-xl:border-t max-xl:border-border/60 max-xl:px-0 max-xl:pt-3 max-xl:pb-1 max-xl:before:font-mono max-xl:before:text-[length:var(--text-2xs)] max-xl:before:tracking-[0.08em] max-xl:before:text-text-muted max-xl:before:content-[attr(data-label)]"
        >
          <ThesisCell holding={holding} />
        </td>

        <td data-label="Shares" className={cn(NUM, 'text-text-secondary')}>
          {formatShares(holding.shares)}
        </td>
        <td data-label="Avg cost" className={cn(NUM, 'text-text-secondary')}>
          {formatMoney(holding.average_cost)}
        </td>

        {/* Every cell below is null — never 0 — when the price could not be
            fetched, and each dash carries the reason on hover. */}
        <td data-label="Price" className={cn(NUM, 'text-text-secondary')}>
          <OrUnavailable
            value={holding.current_price}
            render={formatMoney}
            reason={reason}
          />
        </td>
        {/* Renders nothing at all for an unpriced ticker, but keeps its box, so
            the column stays aligned down the table. */}
        <td
          data-label="30d"
          className="px-3 py-3 max-xl:flex max-xl:items-center max-xl:justify-between max-xl:gap-4 max-xl:px-0 max-xl:py-1 max-xl:before:font-mono max-xl:before:text-[length:var(--text-2xs)] max-xl:before:tracking-[0.08em] max-xl:before:text-text-muted max-xl:before:content-[attr(data-label)]"
        >
          <Sparkline ticker={holding.ticker} days={30} />
        </td>
        <td data-label="Value" className={cn(NUM, 'text-text-primary')}>
          <OrUnavailable
            value={holding.market_value}
            render={formatMoney}
            reason={reason}
          />
        </td>
        <td
          data-label="P&L"
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
            // ⚠️ WRAPPED IN ONE ELEMENT ON PURPOSE. Below md the cell is a flex
            // row of [label, value]; as a bare fragment these two lines would be
            // two separate flex items and the label would end up between the
            // money and the percentage. On desktop a block div holding two block
            // divs renders exactly as the two divs did, so nothing moves there.
            <div>
              <div>{formatSignedMoney(holding.unrealised_pnl)}</div>
              <div className="text-xs opacity-80">
                {formatSignedPercent(holding.pnl_percent)}
              </div>
            </div>
          )}
        </td>
        <td data-label="Alloc" className={cn(NUM, 'text-text-secondary')}>
          <OrUnavailable
            value={holding.allocation_percent}
            render={formatPercent}
            reason={reason}
          />
        </td>

        <td className="px-3 py-3 text-right whitespace-nowrap max-xl:flex max-xl:justify-end max-xl:border-t max-xl:border-border/60 max-xl:px-0 max-xl:pt-3 max-xl:pb-0">
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
        <tr className="max-xl:block">
          <td colSpan={10} className="px-3 pb-3 text-sm text-status-broken max-xl:block max-xl:px-0">
            {error}
          </td>
        </tr>
      )}

      {editing && (
        <tr className="border-b border-border/60 bg-surface-raised/30 max-xl:block max-xl:rounded-xl max-xl:border max-xl:border-border">
          <td colSpan={10} className="px-3 py-4 max-xl:block">
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
        className="inline-flex rounded-xs focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
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
      setProblem(describeError(cause, 'this holding').detail)
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
        className="font-mono text-2xs tracking-[0.08em] text-text-muted uppercase"
      >
        {label}
      </label>
      {children}
    </div>
  )
}
