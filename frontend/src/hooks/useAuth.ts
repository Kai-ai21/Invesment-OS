import { useContext } from 'react'

import { AuthContext, type AuthContextValue } from '@/contexts/AuthContext'

/**
 * The auth context, or a thrown error naming the mistake.
 *
 * Separate from AuthContext.tsx so that file exports only components — Vite's fast
 * refresh warns when a module mixes components with plain functions, and the warning
 * is right: editing a hook would remount the provider and drop the session.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth must be used inside <AuthProvider>')
  }
  return context
}
