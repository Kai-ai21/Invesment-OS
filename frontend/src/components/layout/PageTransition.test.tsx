import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router'

import { PageTransition, usePageLeaving } from '@/components/layout/PageTransition'

/**
 * The hold is a timer, and whether it runs at all depends on a media query —
 * neither of which a browser session can be stepped through. Pinned here instead.
 *
 * The CSS half (that .page-leave and .page-enter animate nothing under reduced
 * motion) lives in the stylesheet's own @media guard and is not this test's job.
 */
describe('PageTransition', () => {
  let reducedMotion = false

  function Harness() {
    return (
      <MemoryRouter initialEntries={['/one']}>
        <PageTransition>
          {(location) => (
            <>
              <Phase />
              <Routes location={location}>
                <Route path="/one" element={<span>page one</span>} />
                <Route path="/two" element={<span>page two</span>} />
              </Routes>
              <GoToTwo />
            </>
          )}
        </PageTransition>
      </MemoryRouter>
    )
  }

  /**
   * A component, not a bare hook call in the render prop — the prop runs in
   * PageTransition's own scope, which is ABOVE the provider. The shell reads the
   * flag the same way this does: from a child.
   */
  function Phase() {
    return <span data-testid="phase">{usePageLeaving() ? 'leaving' : 'settled'}</span>
  }

  function GoToTwo() {
    const navigate = useNavigate()
    return (
      <button type="button" onClick={() => navigate('/two')}>
        go
      </button>
    )
  }

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

  it('holds the outgoing route on screen while it fades, then swaps', () => {
    render(<Harness />)
    expect(screen.getByText('page one')).toBeInTheDocument()

    act(() => screen.getByRole('button').click())

    // Still the page being left, now marked as leaving.
    expect(screen.getByText('page one')).toBeInTheDocument()
    expect(screen.getByTestId('phase')).toHaveTextContent('leaving')

    act(() => void vi.advanceTimersByTime(140))

    expect(screen.getByText('page two')).toBeInTheDocument()
    expect(screen.queryByText('page one')).not.toBeInTheDocument()
    expect(screen.getByTestId('phase')).toHaveTextContent('settled')
  })

  it('swaps on the spot under reduced motion, with no leaving phase', () => {
    reducedMotion = true
    render(<Harness />)

    act(() => screen.getByRole('button').click())

    // No timer advanced: the new route is already the one rendered.
    expect(screen.getByText('page two')).toBeInTheDocument()
    expect(screen.getByTestId('phase')).toHaveTextContent('settled')
  })
})
