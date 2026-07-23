import { useEffect, useRef } from 'react'

export interface NeuralBackgroundProps {
  /** Particle stroke colour. */
  color?: string
  particleCount?: number
  /** Multiplier on how far a particle advances per frame. */
  speed?: number
  /** Alpha of the per-frame background wash — lower leaves longer trails. */
  trailOpacity?: number
  /** Colour washed over the canvas each frame; should match the page background. */
  backgroundColor?: string
  className?: string
}

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  /** Frames until this particle respawns, so the field keeps reorganising. */
  life: number
}

/**
 * Pixels per frame at `speed = 1`. `speed` is a multiplier, not a raw pixel
 * step: at 0.12 trail opacity a streak fades in roughly eight frames, so a
 * sub-pixel step would render as dots rather than a flowing field.
 */
const BASE_SPEED = 2.6

/**
 * A cheap curl-like flow field. Real Perlin noise would be smoother, but two
 * offset trig lobes give the same slowly-turning character for a fraction of
 * the cost, and this runs behind a landing page.
 */
function fieldAngle(x: number, y: number, t: number): number {
  return (
    Math.sin(x * 0.0015 + t) * 1.6 +
    Math.cos(y * 0.0018 - t * 0.8) * 1.6 +
    Math.sin((x + y) * 0.0008 + t * 0.5) * 1.2
  )
}

export function NeuralBackground({
  color = '#ffffff',
  particleCount = 400,
  speed = 0.7,
  trailOpacity = 0.12,
  backgroundColor = '#0f1115',
  className,
}: NeuralBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let width = 0
    let height = 0

    const resize = () => {
      // Cap DPR at 2: past that this is pure cost for an out-of-focus backdrop.
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth
      height = canvas.clientHeight
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.fillStyle = backgroundColor
      ctx.fillRect(0, 0, width, height)
    }

    resize()

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)')

    // Reduced motion: paint a still frame and return before any loop exists.
    // No rAF is ever scheduled, no listeners beyond resize.
    if (reduceMotion.matches) {
      const onResizeStatic = () => resize()
      window.addEventListener('resize', onResizeStatic)
      return () => window.removeEventListener('resize', onResizeStatic)
    }

    const particles: Particle[] = Array.from({ length: particleCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: 0,
      vy: 0,
      life: Math.random() * 200,
    }))

    let frame = 0
    let time = 0
    let running = true

    const step = () => {
      if (!running) return
      time += 0.0015

      // Washing the whole canvas with a low-alpha background colour is what
      // produces the trails; trailOpacity is that alpha.
      ctx.fillStyle = backgroundColor
      ctx.globalAlpha = trailOpacity
      ctx.fillRect(0, 0, width, height)
      ctx.globalAlpha = 1

      ctx.strokeStyle = color
      ctx.lineWidth = 0.75
      ctx.globalAlpha = 0.5
      ctx.beginPath()

      for (const p of particles) {
        const angle = fieldAngle(p.x, p.y, time)
        p.vx = Math.cos(angle) * speed * BASE_SPEED
        p.vy = Math.sin(angle) * speed * BASE_SPEED

        const px = p.x
        const py = p.y
        p.x += p.vx
        p.y += p.vy
        p.life -= 1

        // Respawn off-screen or expired particles somewhere random, and skip the
        // segment so we don't draw a streak across the whole canvas.
        if (p.life <= 0 || p.x < 0 || p.x > width || p.y < 0 || p.y > height) {
          p.x = Math.random() * width
          p.y = Math.random() * height
          p.life = 100 + Math.random() * 200
          continue
        }

        ctx.moveTo(px, py)
        ctx.lineTo(p.x, p.y)
      }

      ctx.stroke()
      ctx.globalAlpha = 1

      frame = requestAnimationFrame(step)
    }

    const start = () => {
      if (running) return
      running = true
      frame = requestAnimationFrame(step)
    }

    const stop = () => {
      running = false
      cancelAnimationFrame(frame)
    }

    // Don't burn CPU behind a hidden tab.
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') stop()
      else start()
    }

    const onResize = () => resize()

    frame = requestAnimationFrame(step)
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('resize', onResize)

    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('resize', onResize)
    }
  }, [color, particleCount, speed, trailOpacity, backgroundColor])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={className}
      style={{ display: 'block', width: '100%', height: '100%' }}
    />
  )
}

export default NeuralBackground
