import { render, type RenderOptions, type RenderResult } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'

import { ToastProvider } from '@/components/ui/toast'
import { TooltipProvider } from '@/components/ui/tooltip'

/**
 * `render` with the app-wide providers that components may reach for.
 *
 * Both of these throw rather than degrade when their provider is missing — a
 * component that raises a toast into nowhere, or a tooltip with no shared delay
 * timer, is a wiring bug worth failing on. That makes them a real dependency of
 * anything that uses them, so tests mount the same pair App.tsx does instead of
 * each test file assembling its own.
 */
function Providers({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <TooltipProvider>{children}</TooltipProvider>
    </ToastProvider>
  )
}

export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>,
): RenderResult {
  return render(ui, { wrapper: Providers, ...options })
}
