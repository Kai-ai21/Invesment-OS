import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react'
import { createPortal } from 'react-dom'
import { Loader2 } from 'lucide-react'

import { Input } from '@/components/ui/input'
import { searchTickers, type TickerMatch } from '@/lib/api'
import { cn } from '@/lib/utils'

/** Matches the backend's MIN_QUERY_LENGTH — one character matches hundreds of
 *  companies, so the dropdown would open on the first keystroke of every ticker. */
const MIN_QUERY_LENGTH = 2

/** Long enough that typing "AMZN" is one request rather than three, short enough
 *  that the list feels attached to the keyboard. */
const DEBOUNCE_MS = 200

export interface TickerInputProps {
  value: string
  onChange: (value: string) => void
  id?: string
  placeholder?: string
  className?: string
  /** Rendered when the field is invalid, so the caller keeps owning validation. */
  'aria-invalid'?: boolean
  autoFocus?: boolean
}

/**
 * Ticker field with SEC-backed autocomplete. ONE component, used by both the
 * new-thesis form and the add-holding form.
 *
 * ⚠️ THE SUGGESTIONS ARE A CONVENIENCE, NEVER A GATE. The user can type any
 * symbol and submit it: the SEC list is comprehensive but not infallible, and a
 * newly listed or unusual ticker must not be un-enterable because a lookup did
 * not know about it. Every failure path here — no matches, a failed request, the
 * backend being down — degrades to "this is a plain text input" rather than
 * blocking or showing an error.
 */
export function TickerInput({
  value,
  onChange,
  id,
  placeholder = 'NVDA',
  className,
  autoFocus,
  'aria-invalid': ariaInvalid,
}: TickerInputProps) {
  const generatedId = useId()
  const inputId = id ?? `ticker-${generatedId}`
  const listboxId = `${inputId}-listbox`

  const [matches, setMatches] = useState<TickerMatch[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  /** True once a lookup failed. The field keeps working; the dropdown stays shut. */
  const [lookupBroken, setLookupBroken] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  /** The company behind the current value, once picked or confirmed by a lookup. */
  const [confirmed, setConfirmed] = useState<TickerMatch | null>(null)
  /** Set while applying a selection, so the resulting value change does not
   *  immediately re-open the dropdown with the thing just chosen. */
  const justSelected = useRef(false)

  const listRef = useRef<HTMLUListElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  /**
   * Viewport coordinates of the input, for the PORTALLED dropdown.
   *
   * ⚠️ WHY A PORTAL. An absolutely-positioned dropdown is clipped by any ancestor
   * with overflow:hidden, and the shadcn Card has exactly that. It happened to look
   * fine inside the tall new-thesis card and was sliced to a 42px sliver inside the
   * short add-holding card — a component built to be dropped anywhere cannot depend
   * on its container's overflow. Rendering to document.body escapes every ancestor,
   * at the cost of positioning it by hand.
   */
  const [anchor, setAnchor] = useState<{ left: number; top: number; width: number } | null>(null)
  const query = value.trim()

  useEffect(() => {
    if (justSelected.current) {
      justSelected.current = false
      return
    }
    if (query.length < MIN_QUERY_LENGTH || lookupBroken) {
      setMatches([])
      setOpen(false)
      return
    }

    let cancelled = false
    setLoading(true)
    const timer = window.setTimeout(() => {
      searchTickers(query)
        .then((results) => {
          if (cancelled) return
          setMatches(results)
          setActiveIndex(-1)
          setOpen(true)
          // A lookup that happens to confirm what was typed fills in the company
          // name without the user having to pick from the list.
          const exact = results.find((r) => r.ticker === query.toUpperCase())
          setConfirmed(exact ?? null)
        })
        .catch(() => {
          if (cancelled) return
          // Silent by design: a broken lookup is not the user's problem and must
          // not look like their ticker was rejected.
          setLookupBroken(true)
          setMatches([])
          setOpen(false)
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }, DEBOUNCE_MS)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [query, lookupBroken])

  // Keep the highlighted row in view when arrowing past the visible window.
  useEffect(() => {
    if (activeIndex < 0) return
    listRef.current?.children[activeIndex]?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex])

  const measure = useCallback(() => {
    const rect = inputRef.current?.getBoundingClientRect()
    if (rect) setAnchor({ left: rect.left, top: rect.bottom + 4, width: rect.width })
  }, [])

  const select = (match: TickerMatch) => {
    justSelected.current = true
    onChange(match.ticker)
    setConfirmed(match)
    setOpen(false)
    setActiveIndex(-1)
  }

  const showDropdown = open && query.length >= MIN_QUERY_LENGTH && !lookupBroken
  const showNoMatch = showDropdown && !loading && matches.length === 0

  // Measure before paint so the list never flashes at a stale position, and keep
  // it pinned while the page scrolls. `true` captures scroll from the scrolling
  // ancestor (<main>), which does not bubble.
  useLayoutEffect(() => {
    if (!showDropdown) return
    measure()
    window.addEventListener('scroll', measure, true)
    window.addEventListener('resize', measure)
    return () => {
      window.removeEventListener('scroll', measure, true)
      window.removeEventListener('resize', measure)
    }
  }, [showDropdown, measure, matches.length, loading])

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setOpen(false)
      setActiveIndex(-1)
      return
    }
    // Enter with nothing highlighted falls through to the form's submit — the
    // dropdown must never swallow a submit from someone who typed a full ticker.
    if (event.key === 'Enter' && showDropdown && activeIndex >= 0) {
      event.preventDefault()
      select(matches[activeIndex])
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      if (!showDropdown || matches.length === 0) return
      event.preventDefault()
      const step = event.key === 'ArrowDown' ? 1 : -1
      setActiveIndex((current) => {
        const next = current + step
        if (next < 0) return matches.length - 1
        if (next >= matches.length) return 0
        return next
      })
    }
  }

  const activeId = activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined
  const help = useMemo(() => {
    if (confirmed) return { text: confirmed.company_name, tone: 'confirmed' as const }
    if (showNoMatch) {
      return { text: 'No match — you can still submit.', tone: 'quiet' as const }
    }
    return null
  }, [confirmed, showNoMatch])

  return (
    <div className={cn('relative', className)}>
      <Input
        ref={inputRef}
        id={inputId}
        value={value}
        autoFocus={autoFocus}
        onChange={(event) => {
          // Upper-cased as they type; tickers are upper-case everywhere in the app
          // and the backend normalises anyway.
          onChange(event.target.value.toUpperCase())
          setConfirmed(null)
        }}
        onKeyDown={handleKeyDown}
        // Re-open on focus only if there is something to show.
        onFocus={() => matches.length > 0 && setOpen(true)}
        // A blur that lands on a suggestion must not close the list before the
        // click registers, hence the delay rather than closing immediately.
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
        aria-invalid={ariaInvalid}
        role="combobox"
        aria-expanded={showDropdown}
        aria-controls={showDropdown ? listboxId : undefined}
        aria-activedescendant={activeId}
        aria-autocomplete="list"
        className="w-full font-mono uppercase"
      />

      {showDropdown && anchor && createPortal(
        <ul
          ref={listRef}
          id={listboxId}
          role="listbox"
          aria-label="Ticker suggestions"
          style={{
            position: 'fixed',
            left: anchor.left,
            top: anchor.top,
            minWidth: Math.max(anchor.width, 224),
          }}
          className="z-50 max-h-56 overflow-y-auto rounded-xl border border-border bg-surface-raised py-1 shadow-lg"
        >
          {loading && (
            // Inside the dropdown, never a page-level spinner — the rest of the
            // form stays usable while this resolves.
            <li className="flex items-center gap-2 px-3 py-2 text-xs text-text-secondary">
              <Loader2 className="size-3 animate-spin" aria-hidden />
              Searching…
            </li>
          )}

          {showNoMatch && (
            <li className="px-3 py-2 text-xs text-text-secondary">
              No match — you can still submit.
            </li>
          )}

          {!loading &&
            matches.map((match, index) => (
              <li
                key={match.ticker}
                id={`${listboxId}-${index}`}
                role="option"
                aria-selected={index === activeIndex}
                // onMouseDown, not onClick: mousedown fires before the input's
                // blur, so the selection lands even though blur closes the list.
                onMouseDown={(event) => {
                  event.preventDefault()
                  select(match)
                }}
                onMouseEnter={() => setActiveIndex(index)}
                className={cn(
                  'flex cursor-pointer items-baseline gap-2.5 px-3 py-1.5',
                  index === activeIndex && 'bg-white/8',
                )}
              >
                <span className="font-mono text-sm text-text-primary">{match.ticker}</span>
                <span className="truncate text-xs text-text-secondary">
                  {match.company_name}
                </span>
              </li>
            ))}
        </ul>,
        document.body,
      )}

      {help && (
        <p
          className={cn(
            'mt-1.5 truncate text-xs',
            help.tone === 'confirmed' ? 'text-text-secondary' : 'text-text-muted',
          )}
        >
          {help.text}
        </p>
      )}
    </div>
  )
}
