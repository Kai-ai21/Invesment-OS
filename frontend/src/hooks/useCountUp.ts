import { useLayoutEffect, useRef, useState } from 'react'

import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'

const DURATION_MS = 700

/** Fast out of the gate, settling into the final digits — cubic ease-out. */
function easeOut(t: number): number {
  return 1 - (1 - t) ** 3
}

/**
 * Counts a figure up from zero the first time it is shown, then tracks it exactly.
 *
 * ⚠️ A NULL IS NEVER ANIMATED. `null` means "we could not price this", and every
 * formatter in lib/format renders it as an em dash. Counting toward it — or from
 * it — would put digits on screen for a number we do not have. Null in, null
 * straight back out, on the same render.
 *
 * ⚠️ NEGATIVES COUNT DOWN. The sweep always starts at zero, so a loss travels
 * 0 → -265 and a gain 0 → +500. It never begins at the worst number and climbs
 * out of it, which would read as the loss having just been recovered.
 *
 * ⚠️ FIRST LOAD ONLY. Once a real number has landed, later values are adopted
 * immediately — a refetch nudging the total by a few cents must not re-run the
 * whole sweep.
 *
 * ⚠️ NOT IN A BACKGROUND TAB. requestAnimationFrame does not tick while the
 * document is hidden, so a sweep started there parks on its first frame — and
 * this sweep's first frame is zero. A five-figure portfolio sitting in an
 * unfocused tab reading "$0.00" is exactly the lie the em-dash rule in
 * lib/format exists to prevent, so a hidden document skips straight to the
 * figure. Nobody is watching the animation anyway.
 */
export function useCountUp(value: number | null, durationMs = DURATION_MS): number | null {
  const reduced = usePrefersReducedMotion()
  const [display, setDisplay] = useState<number | null>(value)
  const played = useRef(false)

  // Layout effect, not a plain one: the first committed value must be the START of
  // the sweep. Running after paint would flash the final figure for a frame and
  // then jump back to zero.
  useLayoutEffect(() => {
    if (value === null) {
      setDisplay(null)
      return
    }
    if (reduced || played.current || document.hidden) {
      setDisplay(value)
      return
    }

    let finished = false
    let frame = 0
    const start = performance.now()

    const step = (now: number) => {
      const t = Math.min((now - start) / durationMs, 1)
      setDisplay(value * easeOut(t))
      if (t < 1) {
        frame = requestAnimationFrame(step)
      } else {
        finished = true
      }
    }

    played.current = true
    setDisplay(0)
    frame = requestAnimationFrame(step)

    return () => {
      cancelAnimationFrame(frame)
      // An interrupted run does not count as having played. Without this, React's
      // StrictMode double-invoke in development would burn the one animation on
      // the throwaway first mount and the real one would snap into place.
      if (!finished) played.current = false
    }
  }, [value, reduced, durationMs])

  return display
}
