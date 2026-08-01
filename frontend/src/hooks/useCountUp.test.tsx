import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCountUp } from '@/hooks/useCountUp'

/**
 * The sweep is driven by requestAnimationFrame against a real clock, which no
 * browser session can be made to step through predictably — so it is pinned here
 * instead, where both can be advanced by hand.
 *
 * These cover the three rules with money on them: a null is never counted toward,
 * a loss travels DOWN from zero rather than up out of itself, and a refetch does
 * not replay the whole thing.
 */
describe('useCountUp', () => {
  let frames: FrameRequestCallback[] = []
  let now = 0
  let reducedMotion = false

  /** Runs every queued frame at `now + ms`, as the browser would. */
  function advanceTo(ms: number) {
    now = ms
    act(() => {
      const due = frames
      frames = []
      due.forEach((frame) => frame(now))
    })
  }

  beforeEach(() => {
    frames = []
    now = 0
    reducedMotion = false

    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) =>
      frames.push(cb),
    )
    vi.stubGlobal('cancelAnimationFrame', () => {})
    vi.spyOn(performance, 'now').mockImplementation(() => now)
    vi.stubGlobal(
      'matchMedia',
      (query: string) => ({
        matches: query.includes('prefers-reduced-motion') && reducedMotion,
        addEventListener: () => {},
        removeEventListener: () => {},
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('starts at zero and settles on the value', () => {
    const { result } = renderHook(() => useCountUp(1000))

    expect(result.current).toBe(0)

    advanceTo(350)
    expect(result.current).toBeGreaterThan(0)
    expect(result.current).toBeLessThan(1000)

    advanceTo(700)
    expect(result.current).toBe(1000)
  })

  it('eases out — more than half the distance is covered in the first half', () => {
    const { result } = renderHook(() => useCountUp(1000))

    advanceTo(350)
    expect(result.current!).toBeGreaterThan(500)
  })

  it('counts a loss DOWN from zero, never up out of it', () => {
    const { result } = renderHook(() => useCountUp(-1403.4))

    expect(result.current).toBe(0)

    advanceTo(200)
    // Below zero and above the final figure: travelling away from zero, not
    // recovering toward it.
    expect(result.current!).toBeLessThan(0)
    expect(result.current!).toBeGreaterThan(-1403.4)

    advanceTo(700)
    expect(result.current).toBe(-1403.4)
  })

  it('never animates a null — no frame is even requested', () => {
    const { result } = renderHook(() => useCountUp(null))

    expect(result.current).toBeNull()
    expect(frames).toHaveLength(0)
  })

  it('adopts a later value without replaying the sweep', () => {
    const { result, rerender } = renderHook(({ value }) => useCountUp(value), {
      initialProps: { value: 1000 },
    })
    advanceTo(700)
    expect(result.current).toBe(1000)

    // A refetch nudges the total; it must land, not sweep.
    rerender({ value: 1002.5 })
    expect(result.current).toBe(1002.5)
    expect(frames).toHaveLength(0)
  })

  it('renders the final value immediately under reduced motion', () => {
    reducedMotion = true
    const { result } = renderHook(() => useCountUp(5096.6))

    expect(result.current).toBe(5096.6)
    expect(frames).toHaveLength(0)
  })

  it('skips the sweep in a hidden document rather than parking on zero', () => {
    // rAF does not tick while hidden, so a started sweep would sit on its first
    // frame — and show a real portfolio as $0.00.
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    const { result } = renderHook(() => useCountUp(5096.6))

    expect(result.current).toBe(5096.6)
    expect(frames).toHaveLength(0)
  })
})
