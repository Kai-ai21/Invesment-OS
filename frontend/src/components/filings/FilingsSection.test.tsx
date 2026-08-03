import { fireEvent, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { FilingsSection } from '@/components/filings/FilingsSection'
import { renderWithProviders } from '@/test/renderWithProviders'
import type { Filing, FilingSummary } from '@/lib/api'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  listFilings: vi.fn(),
  summariseFiling: vi.fn(),
}))

const api = await import('@/lib/api')
const listFilings = vi.mocked(api.listFilings)
const summariseFiling = vi.mocked(api.summariseFiling)

const TEN_Q: Filing = {
  form: '10-Q',
  filing_date: '2026-05-20',
  title: 'NVDA 10-Q 2026-05-20',
  url: 'https://www.sec.gov/Archives/nvda-10q.htm',
  accession_number: '0001045810-26-000052',
}

function summary(overrides: Partial<FilingSummary> = {}): FilingSummary {
  return {
    ticker: 'NVDA',
    filing: TEN_Q,
    filing_type_explained: 'A 10-Q is a quarterly report filed with the SEC.',
    key_points: ['Operating expenses rose.'],
    notable_numbers: [{ figure: '$26.0 billion', what_it_measures: 'revenue' }],
    relevance: [],
    ...overrides,
  }
}

function renderSection(props: Partial<Parameters<typeof FilingsSection>[0]> = {}) {
  return renderWithProviders(
    <MemoryRouter>
      <FilingsSection ticker="NVDA" {...props} />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  listFilings.mockResolvedValue([TEN_Q])
  summariseFiling.mockResolvedValue(summary())
})

/**
 * ⚠️ THESE COVER THE ONE RULE THAT MATTERS: a summary must never read as evidence.
 *
 * The other reason they exist is that `relevance` is almost always empty against a
 * real filing — the model is told an empty list is the expected answer — so the
 * branch that renders a cited claim is the hardest one to reach by driving the
 * running app, and the easiest to leave broken.
 */
describe('FilingsSection', () => {
  it('says what these are before any row is opened', async () => {
    renderSection()
    expect(
      await screen.findByText(/nothing here is checked against your claims/i),
    ).toBeInTheDocument()
  })

  it('renders no status badge anywhere, loaded or expanded', async () => {
    const { container } = renderSection()
    const button = await screen.findByRole('button', { name: /summarise/i })
    fireEvent.click(button)
    await screen.findByText(/A 10-Q is a quarterly report/)

    // StatusBadge is the only thing that sets an inline --status-* colour, which
    // is what makes a row read as a verdict.
    expect(container.innerHTML).not.toContain('--status-')
  })

  it('says the empty relevance case plainly rather than as a failure', async () => {
    renderSection()
    fireEvent.click(await screen.findByRole('button', { name: /summarise/i }))
    expect(
      await screen.findByText("Doesn't directly address your claims."),
    ).toBeInTheDocument()
  })

  it('links a cited claim to its thesis, and says relevance is not a verdict', async () => {
    summariseFiling.mockResolvedValue(
      summary({
        relevance: [
          { claim_id: 'c1', thesis_id: 't1', statement: 'Margins hold above 70%.' },
        ],
      }),
    )
    renderSection()
    fireEvent.click(await screen.findByRole('button', { name: /summarise/i }))

    const link = await screen.findByRole('link', { name: 'Margins hold above 70%.' })
    expect(link).toHaveAttribute('href', '/theses/t1')
    // "talks about", never "supports" — the summary was not checked against it.
    expect(screen.getByText(/Whether it supports them is a separate question/i))
      .toBeInTheDocument()
  })

  it('renders a cited claim as plain text where linking would point at this page', async () => {
    summariseFiling.mockResolvedValue(
      summary({
        relevance: [
          { claim_id: 'c1', thesis_id: 't1', statement: 'Margins hold above 70%.' },
        ],
      }),
    )
    renderSection({ linkClaims: false })
    fireEvent.click(await screen.findByRole('button', { name: /summarise/i }))

    expect(await screen.findByText('Margins hold above 70%.')).toBeInTheDocument()
    expect(
      screen.queryByRole('link', { name: 'Margins hold above 70%.' }),
    ).not.toBeInTheDocument()
  })

  it('pairs every figure with what it measures', async () => {
    renderSection()
    fireEvent.click(await screen.findByRole('button', { name: /summarise/i }))
    const figure = await screen.findByText('$26.0 billion')
    expect(figure.tagName).toBe('DT')
    expect(figure.nextElementSibling).toHaveTextContent('revenue')
  })

  it('says how long the read takes rather than spinning silently', async () => {
    let resolve: (value: FilingSummary) => void = () => {}
    summariseFiling.mockReturnValue(
      new Promise<FilingSummary>((r) => {
        resolve = r
      }),
    )
    renderSection()
    fireEvent.click(await screen.findByRole('button', { name: /summarise/i }))

    expect(await screen.findByText(/Reading the filing/)).toBeInTheDocument()
    expect(screen.getByText(/10-20 seconds/)).toBeInTheDocument()
    resolve(summary())
  })

  it('does not re-request a summary it has already read', async () => {
    renderSection()
    const button = await screen.findByRole('button', { name: /summarise/i })
    fireEvent.click(button)
    await screen.findByText(/A 10-Q is a quarterly report/)

    // Collapse, then reopen. A summary costs an AI call and 10-20 seconds; paying
    // for it twice because someone closed a row is the bug this guards.
    fireEvent.click(screen.getByRole('button', { name: /summary/i }))
    await waitFor(() =>
      expect(screen.queryByText(/A 10-Q is a quarterly report/)).not.toBeInTheDocument(),
    )
    fireEvent.click(screen.getByRole('button', { name: /summarise|summary/i }))

    await screen.findByText(/A 10-Q is a quarterly report/)
    expect(summariseFiling).toHaveBeenCalledTimes(1)
  })

  it('keeps a failed row inline, leaving the rest of the list usable', async () => {
    summariseFiling.mockRejectedValue(new Error('boom'))
    renderSection()
    fireEvent.click(await screen.findByRole('button', { name: /summarise/i }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    // The list itself is untouched — the row is still there to try again.
    expect(screen.getByText('NVDA 10-Q 2026-05-20')).toBeInTheDocument()
  })

  it('treats an empty filing list as a normal answer, not an error', async () => {
    listFilings.mockResolvedValue([])
    renderSection()
    expect(
      await screen.findByText(/No recent 10-K, 10-Q or 8-K filings for NVDA/),
    ).toBeInTheDocument()
  })
})
