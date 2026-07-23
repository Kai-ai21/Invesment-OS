import { useOutletContext } from 'react-router'

export interface ShellContext {
  /**
   * Re-reads the unread count behind the sidebar badge. Pages call this after
   * changing read state so the badge doesn't drift — this is the only refresh
   * there is, deliberately: no polling.
   */
  refreshUnreadCount: () => Promise<void>
}

export function useShellContext(): ShellContext {
  return useOutletContext<ShellContext>()
}
