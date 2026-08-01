import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { PostMortem } from '@/lib/api'

// Mocked before the component is imported, so nothing touches the network.
vi.mock('@/lib/api', () => ({
  listPostMortemsForThesis: vi.fn(),
  listPostMortems: vi.fn(),
  generateQuestion: vi.fn(),
  answerPostMortem: vi.fn(),
  deletePostMortem: vi.fn(),
}))

// The block reads the shell context for the sidebar badge; stub it so the component
// can render outside a router.
vi.mock('@/hooks/useShellContext', () => ({
  useShellContext: () => ({
    refreshUnreadCount: vi.fn(),
    refreshPendingReflections: vi.fn(),
  }),
}))

import { generateQuestion, listPostMortemsForThesis } from '@/lib/api'
import { ThesisReflections } from '@/components/reflection/ThesisReflections'
// Reflection cards raise a toast on save and delete, and their status badges
// carry tooltips — both need their providers mounted.
import { renderWithProviders } from '@/test/renderWithProviders'

const THESIS_ID = 'thesis-1'
const CLAIM_STATEMENT = 'Nvidia sustains high gross margins.'

/**
 * A post-mortem in the state the backend actually creates it in: BOTH
 * prompt_question and user_response null. The question is written lazily on display;
 * a null response is what "pending" means.
 */
function pendingPostMortem(overrides: Partial<PostMortem> = {}): PostMortem {
  return {
    id: 'pm-1',
    thesis_id: THESIS_ID,
    ticker: 'NVDA',
    logo_url: 'https://icons.duckduckgo.com/ip3/nvidia.com.ico',
    broken_claim_id: 'claim-1',
    broken_claim_statement: CLAIM_STATEMENT,
    prompt_question: null,
    user_response: null,
    status_at_break: 'breaking',
    created_at: '2026-07-27T12:00:00Z',
    answered_at: null,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  // Never resolves, so the card stays in its "Preparing your question…" state — it
  // must be usable before any question exists.
  vi.mocked(generateQuestion).mockImplementation(() => new Promise(() => {}))
})

describe('ThesisReflections', () => {
  it('renders a post-mortem with null question AND null response as a pending card', async () => {
    // Arrange — the exact shape that was rendering nothing.
    vi.mocked(listPostMortemsForThesis).mockResolvedValue([pendingPostMortem()])

    // Act
    renderWithProviders(<ThesisReflections thesisId={THESIS_ID} />)

    // Assert — the card is present, showing the claim it is about...
    expect(await screen.findByText(CLAIM_STATEMENT)).toBeInTheDocument()

    // ...and is treated as PENDING, not answered: an answer box, not a saved answer.
    expect(screen.getByPlaceholderText(/what were you thinking/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /skip for now/i })).toBeInTheDocument()
    expect(screen.queryByText(/your answer/i)).not.toBeInTheDocument()
  })

  it('renders the card BEFORE a question exists, then asks for one', async () => {
    // Arrange — guards against a deadlock: if the card required prompt_question in
    // order to render, the question could never be generated, because generation is
    // triggered by the card itself.
    vi.mocked(listPostMortemsForThesis).mockResolvedValue([pendingPostMortem()])

    // Act
    renderWithProviders(<ThesisReflections thesisId={THESIS_ID} />)
    await screen.findByText(CLAIM_STATEMENT)

    // Assert. findBy, not getBy: "Preparing…" is set by the generation EFFECT, which
    // React runs after the commit that put the claim on screen — so the card can be
    // present for a tick before the flag it depends on is.
    expect(await screen.findByText(/preparing your question/i)).toBeInTheDocument()
    expect(generateQuestion).toHaveBeenCalledWith('pm-1')
  })

  it('shows a newly pending card when the list changes after mount, without a reload', async () => {
    // Arrange — the reported bug. A check breaks the thesis, the backend opens a
    // post-mortem, and it must appear without the user reloading the page. The page
    // re-reads by remounting this block with a changed key, which is what the key
    // change below reproduces.
    vi.mocked(listPostMortemsForThesis).mockResolvedValue([])
    const { rerender } = renderWithProviders(
      <ThesisReflections key="0" thesisId={THESIS_ID} />,
    )

    // Nothing to show at first.
    await waitFor(() => expect(listPostMortemsForThesis).toHaveBeenCalledTimes(1))
    expect(screen.queryByText(CLAIM_STATEMENT)).not.toBeInTheDocument()

    // Act — the server now has one, and the key changes as it does after a check.
    vi.mocked(listPostMortemsForThesis).mockResolvedValue([pendingPostMortem()])
    rerender(<ThesisReflections key="1" thesisId={THESIS_ID} />)

    // Assert — the card appears, with no page reload involved.
    expect(await screen.findByText(CLAIM_STATEMENT)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument()
  })

  it('does not render an answered post-mortem as pending', async () => {
    // Arrange — the mirror of the first test, so a component that simply treated
    // everything as pending would fail here.
    vi.mocked(listPostMortemsForThesis).mockResolvedValue([
      pendingPostMortem({
        user_response: 'I anchored on one quarter.',
        answered_at: '2026-07-27T13:00:00Z',
        prompt_question: 'What made you confident?',
      }),
    ])

    // Act
    renderWithProviders(<ThesisReflections thesisId={THESIS_ID} />)

    // Assert — collapsed behind "Past reflections", with no answer box.
    expect(await screen.findByText(/past reflections \(1\)/i)).toBeInTheDocument()
    expect(
      screen.queryByPlaceholderText(/what were you thinking/i),
    ).not.toBeInTheDocument()
  })
})
