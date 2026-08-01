import { useEffect, useId, useState } from 'react'

import { loadPriceHistory } from '@/lib/priceHistory'
import { cn } from '@/lib/utils'

const DEFAULT_DAYS = 30
const DEFAULT_WIDTH = 64
const DEFAULT_HEIGHT = 20
/** Half the stroke, so the line's own width never clips at the top or bottom. */
const PADDING = 1

/**
 * A price line at glance size: no axes, no grid, no labels, no tooltip. It says
 * "this is the shape of the last month" and nothing more precise — the detail
 * chart on the thesis page is where a number can actually be read off.
 *
 * ⚠️ NEVER COLOURED BY DIRECTION. The obvious move is green when it ends higher
 * and red when it ends lower, and it is wrong HERE specifically: green and red
 * already mean supported and broken on every card this sits on, and a rising
 * price on a thesis that is falling apart would paint the card green and say the
 * opposite of the truth. The line is the same neutral accent as the main chart,
 * always. Direction is legible from the shape, which is what a sparkline is for.
 */
export function Sparkline({
  ticker,
  days = DEFAULT_DAYS,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  className,
}: {
  ticker: string
  days?: number
  width?: number
  height?: number
  className?: string
}) {
  const [points, setPoints] = useState<number[] | null>(null)

  // Two gradients per instance, matching PriceChart's: ids are document-global,
  // and a list renders many of these at once.
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '')
  const fillId = `spark-fill-${uid}`
  const strokeId = `spark-stroke-${uid}`

  useEffect(() => {
    let cancelled = false
    loadPriceHistory(ticker, days)
      .then((history) => {
        if (!cancelled) setPoints(history?.points.map((p) => p.close) ?? [])
      })
      // A failure and an empty series render identically — as nothing. There is
      // no useful way to say "the price feed is down" in 64 by 20 pixels, and the
      // row this sits in has its own error handling for anything that matters.
      .catch(() => {
        if (!cancelled) setPoints([])
      })
    return () => {
      cancelled = true
    }
  }, [ticker, days])

  const path = points && points.length >= 2 ? buildPath(points, width, height) : null

  // ⚠️ THE BOX IS ALWAYS RENDERED, at its full size, even with nothing in it.
  // A sparkline that appears when the data arrives would reflow every row of the
  // list a second after it painted. Empty is a state this occupies, not one it
  // collapses out of — and it is EMPTY, never a flat line, which would claim a
  // price that did not move rather than one we do not have.
  return (
    <span
      className={cn('inline-block shrink-0 align-middle', className)}
      style={{ width, height }}
      aria-hidden
    >
      {path && (
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="none">
          <defs>
            {/* Vertical: weight under the line, gone by the baseline. */}
            <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.18} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
            </linearGradient>
            {/* Horizontal, oldest to newest — the same fade as the detail chart,
                so the two read as the same object at two sizes. Bottoms out at
                0.35 for the same reason: history is de-emphasised, not erased. */}
            <linearGradient id={strokeId} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={1} />
            </linearGradient>
          </defs>

          <path d={path.area} fill={`url(#${fillId})`} />
          <path
            d={path.line}
            fill="none"
            stroke={`url(#${strokeId})`}
            strokeWidth={1.25}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </span>
  )
}

/**
 * Closes to an SVG path, scaled to fill the box.
 *
 * Scaled to the series' OWN min and max rather than to zero: at this size a
 * zero-based axis would flatten every real move into a straight line, which is
 * the one thing this must never draw. A dead-flat series (every close identical)
 * is centred rather than divided by a zero range.
 */
function buildPath(
  closes: number[],
  width: number,
  height: number,
): { line: string; area: string } {
  const min = Math.min(...closes)
  const max = Math.max(...closes)
  const range = max - min

  const usable = height - PADDING * 2
  const x = (index: number) => (index / (closes.length - 1)) * width
  const y = (close: number) =>
    range === 0 ? height / 2 : PADDING + (1 - (close - min) / range) * usable

  const line = closes
    .map((close, index) => `${index === 0 ? 'M' : 'L'}${x(index).toFixed(2)},${y(close).toFixed(2)}`)
    .join(' ')

  // The fill closes down to the bottom edge, so the area sits under the line
  // rather than between the line and its own minimum.
  const area = `${line} L${width},${height} L0,${height} Z`

  return { line, area }
}
