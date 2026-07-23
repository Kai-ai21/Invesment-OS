import { useEffect, useRef, type ReactNode } from 'react'
import { Mesh, Program, Renderer, Triangle } from 'ogl'

const VERTEX = /* glsl */ `
  attribute vec2 uv;
  attribute vec2 position;
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position, 0.0, 1.0);
  }
`

const FRAGMENT = /* glsl */ `
  precision highp float;

  varying vec2 vUv;
  uniform float uTime;
  uniform float uHover;
  uniform vec2 uMouse;
  uniform vec2 uResolution;

  float roundedBoxSDF(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
  }

  void main() {
    vec2 px = (vUv - 0.5) * uResolution;
    float radius = min(uResolution.y * 0.5, 24.0);
    float d = roundedBoxSDF(px, uResolution * 0.5 - 1.0, radius);
    float alpha = 1.0 - smoothstep(-1.0, 1.0, d);
    if (alpha <= 0.001) discard;

    // Monochrome accent (#e8eaf0) — the same primary as the rest of the app.
    vec3 base = vec3(0.910, 0.918, 0.941);

    // Aspect-corrected so the specular lobe stays circular on a wide button.
    float aspect = uResolution.x / max(uResolution.y, 1.0);
    vec2 p = vec2(vUv.x * aspect, vUv.y);
    vec2 m = vec2(uMouse.x * aspect, uMouse.y);
    float spec = exp(-distance(p, m) * 5.0) * (0.10 + 0.30 * uHover);

    // Slow travelling sheen, so the surface reads as lit even without a pointer.
    float sheen = smoothstep(0.4, 0.55, sin(vUv.x * 3.0 - uTime * 0.9)) * 0.06;

    float edge = smoothstep(2.0, 0.0, abs(d)) * 0.18;

    gl_FragColor = vec4(base + spec + sheen + edge, alpha);
  }
`

export interface SpecularButtonProps {
  children: ReactNode
  onClick?: () => void
  className?: string
}

/**
 * WebGL specular surface behind a button label.
 *
 * Each instance allocates its own WebGL context, and browsers cap how many can
 * exist at once — keep this to the single landing CTA. Every in-app button is a
 * plain shadcn `Button`.
 */
export function SpecularButton({ children, onClick, className }: SpecularButtonProps) {
  const hostRef = useRef<HTMLSpanElement>(null)
  const hoverRef = useRef(0)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)')

    const renderer = new Renderer({
      alpha: true,
      dpr: Math.min(window.devicePixelRatio || 1, 2),
    })
    const gl = renderer.gl
    gl.clearColor(0, 0, 0, 0)

    const canvas = gl.canvas as HTMLCanvasElement
    canvas.style.position = 'absolute'
    canvas.style.inset = '0'
    canvas.style.width = '100%'
    canvas.style.height = '100%'
    host.appendChild(canvas)

    const program = new Program(gl, {
      vertex: VERTEX,
      fragment: FRAGMENT,
      transparent: true,
      uniforms: {
        uTime: { value: 0 },
        uHover: { value: 0 },
        uMouse: { value: [0.5, 0.5] },
        uResolution: { value: [1, 1] },
      },
    })
    const mesh = new Mesh(gl, { geometry: new Triangle(gl), program })

    const resize = () => {
      const { width, height } = host.getBoundingClientRect()
      if (width === 0 || height === 0) return
      renderer.setSize(width, height)
      program.uniforms.uResolution.value = [width, height]
      renderer.render({ scene: mesh })
    }

    const observer = new ResizeObserver(resize)
    observer.observe(host)
    resize()

    // Pointer tracking is cheap and harmless under reduced motion — it's the
    // continuous loop below that we skip.
    const onPointerMove = (event: PointerEvent) => {
      const rect = host.getBoundingClientRect()
      program.uniforms.uMouse.value = [
        (event.clientX - rect.left) / rect.width,
        1 - (event.clientY - rect.top) / rect.height,
      ]
      if (reduceMotion.matches) renderer.render({ scene: mesh })
    }
    const onEnter = () => {
      hoverRef.current = 1
    }
    const onLeave = () => {
      hoverRef.current = 0
      program.uniforms.uMouse.value = [0.5, 0.5]
    }

    host.addEventListener('pointermove', onPointerMove)
    host.addEventListener('pointerenter', onEnter)
    host.addEventListener('pointerleave', onLeave)

    let frame = 0
    let running = false
    const startedAt = performance.now()

    const step = () => {
      if (!running) return
      program.uniforms.uTime.value = (performance.now() - startedAt) / 1000
      // Ease toward the hover target so entering/leaving isn't a hard step.
      const current = program.uniforms.uHover.value as number
      program.uniforms.uHover.value = current + (hoverRef.current - current) * 0.08
      renderer.render({ scene: mesh })
      frame = requestAnimationFrame(step)
    }

    const start = () => {
      if (running || reduceMotion.matches) return
      running = true
      frame = requestAnimationFrame(step)
    }
    const stop = () => {
      running = false
      cancelAnimationFrame(frame)
    }

    const onVisibility = () => {
      if (document.visibilityState === 'hidden') stop()
      else start()
    }
    document.addEventListener('visibilitychange', onVisibility)

    if (reduceMotion.matches) {
      // One static frame, no loop.
      renderer.render({ scene: mesh })
    } else {
      start()
    }

    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
      host.removeEventListener('pointermove', onPointerMove)
      host.removeEventListener('pointerenter', onEnter)
      host.removeEventListener('pointerleave', onLeave)
      observer.disconnect()
      canvas.remove()
      // Free the context rather than waiting for GC to reclaim it.
      gl.getExtension('WEBGL_lose_context')?.loseContext()
    }
  }, [])

  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'group relative isolate inline-flex h-11 items-center justify-center rounded-[22px] px-7 ' +
        'text-sm font-medium text-background transition-transform active:translate-y-px ' +
        'focus-visible:ring-3 focus-visible:ring-ring/60 focus-visible:outline-none ' +
        (className ?? '')
      }
    >
      {/* The GL surface is decorative; the button itself carries the semantics. */}
      <span ref={hostRef} aria-hidden className="absolute inset-0 -z-10 rounded-[22px]" />
      {/* Painted before WebGL initialises, and the whole button if WebGL is
          unavailable — so the CTA is never an invisible hit area. */}
      <span aria-hidden className="absolute inset-0 -z-20 rounded-[22px] bg-primary" />
      {children}
    </button>
  )
}

export default SpecularButton
