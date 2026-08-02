// Adds the jest-dom matchers (toBeInTheDocument, toHaveTextContent, ...) to Vitest's
// expect. Loaded via `setupFiles` in vite.config.ts, so tests need not import it.
import '@testing-library/jest-dom/vitest'

/**
 * jsdom implements no ResizeObserver, and referencing the missing constructor throws
 * during render — which blanks the whole tree and fails the test with a confusing
 * "unable to find text" rather than naming the real cause.
 *
 * TruncatedText needs it: it measures scrollWidth against clientWidth to decide
 * whether a string is actually clipped, and re-measures when the element resizes.
 *
 * The stub deliberately never fires the callback. jsdom has no layout engine, so
 * every width it reports is 0 and any measurement taken here would be fiction — the
 * component's first, synchronous measure already runs and reads 0 === 0, i.e. "not
 * clipped". Truncation behaviour is verified in the browser, not here; this exists
 * so that components using it can be rendered at all.
 */
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver
