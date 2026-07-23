import { motion, useReducedMotion } from 'motion/react'

export interface ShinyTextProps {
  text: string
  /** Base text colour. */
  color?: string
  /** Colour of the highlight that sweeps across. */
  shineColor?: string
  /** Seconds per sweep. */
  speed?: number
  className?: string
}

/**
 * A single sweeping highlight across text. Reserved for the app name — never
 * put this on data, tickers, statuses, or list items.
 */
export function ShinyText({
  text,
  color = '#b5b5b5',
  shineColor = '#ffffff',
  speed = 3,
  className,
}: ShinyTextProps) {
  const reduceMotion = useReducedMotion()

  const gradient = `linear-gradient(100deg, ${color} 40%, ${shineColor} 50%, ${color} 60%)`

  // With reduced motion the sweep is dropped entirely and the text renders in
  // the flat base colour — a stalled gradient would leave a bright band.
  if (reduceMotion) {
    return (
      <span className={className} style={{ color }}>
        {text}
      </span>
    )
  }

  return (
    <motion.span
      className={className}
      style={{
        backgroundImage: gradient,
        backgroundSize: '250% 100%',
        WebkitBackgroundClip: 'text',
        backgroundClip: 'text',
        color: 'transparent',
        display: 'inline-block',
      }}
      initial={{ backgroundPositionX: '150%' }}
      animate={{ backgroundPositionX: '-150%' }}
      transition={{ duration: speed, repeat: Infinity, ease: 'linear' }}
    >
      {text}
    </motion.span>
  )
}

export default ShinyText
