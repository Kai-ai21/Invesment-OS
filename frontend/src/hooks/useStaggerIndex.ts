import { useEffect, useState } from 'react'

import { STAGGER_TOTAL_MS } from '@/lib/motion'

/**
 * Hands each row its position in the entry sequence, and then stops.
 *
 * ⚠️ WHY THIS EXISTS AT ALL — a CSS animation runs when its element is created,
 * so it is tempting to think stable React keys are enough to make an entrance
 * play once. They are not. Re-ordering a keyed list makes React MOVE the node,
 * and a move is a remove followed by an insert: the element leaves the document,
 * its animation is cancelled, and re-insertion starts a fresh one. Re-sorting the
 * holdings table replayed the entrance on every row that changed place, dropping
 * it to opacity 0 and fading it back in.
 *
 * So the arming is time-boxed instead. Once the sequence has had long enough to
 * finish, this returns `undefined` for every row, the class comes off, and there
 * is no animation left for a move — or anything else — to restart.
 *
 * Stable-key re-renders (marking an alert read, a price refresh) never restarted
 * anything to begin with; this covers the reorder case on top of that.
 *
 * @param ready whether the list is rendering its items yet. The clock starts when
 *   this first turns true, NOT at mount — a page that shows a skeleton for 800ms
 *   would otherwise spend its whole entrance budget before the rows exist.
 */
export function useStaggerIndex(ready: boolean): (index: number) => number | undefined {
  const [armed, setArmed] = useState(true)

  useEffect(() => {
    if (!ready || !armed) return
    const timer = setTimeout(() => setArmed(false), STAGGER_TOTAL_MS)
    return () => clearTimeout(timer)
  }, [ready, armed])

  return (index) => (armed && ready ? index : undefined)
}
