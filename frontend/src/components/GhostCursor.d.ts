import type { CSSProperties, ReactElement } from 'react'

/**
 * Types for the vendored GhostCursor.jsx (shadcn @react-bits). The runtime is
 * the .jsx; this sibling declaration lets the strict TS build import it without
 * enabling allowJs. Only the props this app passes are documented here.
 */
export interface GhostCursorProps {
  className?: string
  style?: CSSProperties
  trailLength?: number
  inertia?: number
  grainIntensity?: number
  bloomStrength?: number
  bloomRadius?: number
  bloomThreshold?: number
  brightness?: number
  color?: string
  mixBlendMode?: string
  edgeIntensity?: number
  maxDevicePixelRatio?: number
  targetPixels?: number
  fadeDelayMs?: number
  fadeDurationMs?: number
  zIndex?: number
}

declare const GhostCursor: (props: GhostCursorProps) => ReactElement
export default GhostCursor
