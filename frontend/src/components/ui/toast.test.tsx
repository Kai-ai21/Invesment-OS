import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ToastProvider, useToast } from '@/components/ui/toast'

/**
 * The stack's rules are about TIME — a 4s timer, a hover that banks the balance
 * of it, an exit that is skipped under reduced motion. None of those can be
 * stepped through in a browser session, so they are pinned here.
 */
describe('toasts', () => {
  let reducedMotion = false

  /** Raises toasts on demand from inside the provider. */
  function Harness() {
    const toast = useToast()
    return (
      <>
        <button type="button" onClick={() => toast.success('saved')}>
          ok
        </button>
        <button type="button" onClick={() => toast.error('broke')}>
          fail
        </button>
        <button type="button" onClick={() => toast.info('noted')}>
          note
        </button>
      </>
    )
  }

  function setup() {
    render(
      <ToastProvider>
        <Harness />
      </ToastProvider>,
    )
  }

  const click = (name: string) =>
    act(() => screen.getByRole('button', { name }).click())

  const stack = () =>
    Array.from(document.querySelectorAll('[aria-live="polite"] > *'))

  beforeEach(() => {
    vi.useFakeTimers()
    reducedMotion = false
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: query.includes('prefers-reduced-motion') && reducedMotion,
      addEventListener: () => {},
      removeEventListener: () => {},
    }))
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('keeps the live region mounted before anything is announced', () => {
    setup()
    // An aria-live region added at the same moment as its first message is not
    // observed by assistive tech — it has to already be there.
    expect(document.querySelector('[aria-live="polite"]')).toBeInTheDocument()
    expect(stack()).toHaveLength(0)
  })

  it('uses role=status for success and info, role=alert for errors', () => {
    setup()
    click('ok')
    click('note')
    click('fail')

    expect(stack().map((el) => el.getAttribute('role'))).toEqual([
      'status',
      'status',
      'alert',
    ])
  })

  it('caps at three, dropping the oldest and keeping the newest at the bottom', () => {
    setup()
    click('ok')
    click('note')
    click('fail')
    click('ok')

    const texts = stack().map((el) => el.textContent)
    expect(texts).toHaveLength(3)
    // The first "saved" has gone; the second is last, nearest the corner.
    expect(texts[0]).toContain('noted')
    expect(texts[1]).toContain('broke')
    expect(texts[2]).toContain('saved')
  })

  it('dismisses itself after four seconds', () => {
    setup()
    click('ok')
    expect(stack()).toHaveLength(1)

    act(() => void vi.advanceTimersByTime(4000))
    // Plus the exit fade.
    act(() => void vi.advanceTimersByTime(200))
    expect(stack()).toHaveLength(0)
  })

  it('pauses the timer while hovered, and resumes with the balance', () => {
    setup()
    click('ok')

    act(() => void vi.advanceTimersByTime(3000))
    act(() => stack()[0].dispatchEvent(new MouseEvent('mouseover', { bubbles: true })))

    // Well past the original four seconds, and still up.
    act(() => void vi.advanceTimersByTime(20000))
    expect(stack()).toHaveLength(1)

    act(() => stack()[0].dispatchEvent(new MouseEvent('mouseout', { bubbles: true })))
    // Only the 1s balance is left, not a fresh 4s.
    act(() => void vi.advanceTimersByTime(1000))
    act(() => void vi.advanceTimersByTime(200))
    expect(stack()).toHaveLength(0)
  })

  it('closes on the dismiss button', () => {
    setup()
    click('ok')
    click('note')

    act(() => screen.getAllByRole('button', { name: /dismiss notification/i })[0].click())
    act(() => void vi.advanceTimersByTime(200))

    expect(stack()).toHaveLength(1)
    expect(stack()[0].textContent).toContain('noted')
  })

  it('skips the exit animation under reduced motion', () => {
    reducedMotion = true
    setup()
    click('ok')

    act(() => screen.getByRole('button', { name: /dismiss notification/i }).click())
    // Gone on the spot — no 160ms fade to sit through when there is no fade.
    expect(stack()).toHaveLength(0)
  })
})
