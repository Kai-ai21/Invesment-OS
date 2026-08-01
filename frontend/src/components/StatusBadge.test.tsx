import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatusBadge } from '@/components/StatusBadge'
// The badge now carries a tooltip explaining its status, so it needs the
// provider that owns the shared open delay.
import { renderWithProviders } from '@/test/renderWithProviders'

/**
 * The pulse is the one piece of this motion pass that cannot be exercised by
 * driving the running app: a thesis status only changes when the backend
 * re-verifies it. These cover the rule that actually matters — the badge must
 * stay still unless the value under it moved.
 */
describe('StatusBadge pulse', () => {
  const pulseClass = 'status-pulse'

  it('does not pulse on first render', () => {
    renderWithProviders(<StatusBadge status="breaking" />)
    expect(screen.getByText('breaking')).not.toHaveClass(pulseClass)
  })

  it('does not pulse when re-rendered with the same status', () => {
    const { rerender } = renderWithProviders(<StatusBadge status="weakening" />)
    rerender(<StatusBadge status="weakening" />)
    expect(screen.getByText('weakening')).not.toHaveClass(pulseClass)
  })

  it('pulses when the status changes while mounted', () => {
    const { rerender } = renderWithProviders(<StatusBadge status="weakening" />)
    rerender(<StatusBadge status="breaking" />)
    expect(screen.getByText('breaking')).toHaveClass(pulseClass)
  })

  it('flashes in the colour of the status just arrived at', () => {
    const { rerender } = renderWithProviders(<StatusBadge status="weakening" />)
    rerender(<StatusBadge status="breaking" />)
    // --status-broken, not --status-weakening: the glow is about where it landed.
    expect(screen.getByText('breaking').getAttribute('style')).toContain(
      'var(--status-broken)',
    )
  })
})
