import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * The pipeline, in the order it actually runs. A cold research request does a
 * filing fetch, two retrieval passes and an AI call, so the wait is 10-20 seconds
 * — long enough that a bare spinner reads as "broken".
 *
 * ⚠️ THESE ARE NOT PROGRESS REPORTS. The endpoint is a single request and tells us
 * nothing about which stage it has reached, so these are elapsed-time cues for
 * work we know is happening in this order. They are worded to stay TRUE at any
 * moment they are on screen: "Reading the latest SEC filing" describes the job,
 * not a completed step, and the wording never claims a stage has finished. The
 * last one has no successor, so an unusually slow request cannot leave a stale
 * claim on screen.
 *
 * "SEC filing" rather than "10-K": the backend takes the best of a 10-K, 10-Q or
 * 8-K, and which one it found is not known until the response arrives. Naming the
 * form here would be a guess a quarter of the time — the footer states the real
 * document once we have it.
 */
/** Thresholds fitted to MEASURED cold runs, not guessed: 17s for a small-cap 10-K
 *  (CRSR) and 31s for a large one (NVDA), on 2026-07-29. */
const STAGES = [
  { after: 0, label: 'Looking up the company…' },
  { after: 4, label: 'Reading the latest SEC filing…' },
  { after: 10, label: 'Finding the passages that describe the business…' },
  { after: 18, label: 'Writing the summary…' },
] as const

export function ResearchLoading({ ticker }: { ticker: string }) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [])

  // The last stage whose threshold has passed.
  const stage = [...STAGES].reverse().find((entry) => seconds >= entry.after) ?? STAGES[0]

  return (
    <div aria-busy="true" aria-live="polite">
      <Card className="mb-6 [--card-spacing:--spacing(6)]">
        <div className="flex flex-col gap-3 px-(--card-spacing)">
          <div className="flex items-center gap-2.5 text-sm text-text-primary">
            <Loader2 className="size-4 animate-spin text-text-secondary" aria-hidden />
            {stage.label}
          </div>
          <p className="text-xs text-text-secondary">
            Reading {ticker}'s own filing rather than summarising from memory. The
            first look usually takes 15–35 seconds, then it's cached for a day.
          </p>
        </div>
      </Card>

      {/* Card-shaped placeholders, so the page does not jump when they resolve. */}
      <div className="flex flex-col gap-4">
        {[0, 1, 2].map((index) => (
          <Card key={index} className="[--card-spacing:--spacing(6)]">
            <div className="flex flex-col gap-2.5 px-(--card-spacing)">
              <Skeleton className="h-3 w-40" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-11/12" />
              <Skeleton className="h-4 w-4/6" />
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
