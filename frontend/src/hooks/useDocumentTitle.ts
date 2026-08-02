import { useEffect } from 'react'

/** Matches the <title> in index.html, which is what shows before React mounts. */
export const APP_NAME = 'Kailaas OS'

/**
 * Sets the browser tab's title for the current route.
 *
 * Every page shared one title before this — "Kailaas OS" on all nine — which makes
 * the app unusable in the two places a title is the ONLY label you get: a row of
 * pinned tabs, and browser history. "NVDA — Kailaas OS" is legible in both.
 *
 * Pass null while the page's own subject is still loading, so a detail page shows
 * the plain app name rather than flashing "undefined" or a stale ticker on its way
 * to the right one.
 *
 * No cleanup on unmount, deliberately: every route sets its own title, so restoring
 * the previous one would only introduce a frame of the wrong text mid-navigation.
 */
export function useDocumentTitle(title: string | null): void {
  useEffect(() => {
    document.title = title ? `${title} — ${APP_NAME}` : APP_NAME
  }, [title])
}
