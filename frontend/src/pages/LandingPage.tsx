import { useNavigate } from 'react-router'

import { NeuralBackground } from '@/components/effects/NeuralBackground'
import { ShinyText } from '@/components/effects/ShinyText'
import { SpecularButton } from '@/components/effects/SpecularButton'

/**
 * The only route with particles or WebGL. Everything past the CTA is flat,
 * functional chrome.
 */
export function LandingPage() {
  const navigate = useNavigate()

  return (
    <div className="relative h-screen overflow-hidden bg-background">
      <div className="absolute inset-0">
        <NeuralBackground
          color="#ffffff"
          particleCount={400}
          speed={0.7}
          trailOpacity={0.12}
          backgroundColor="#0f1115"
        />
      </div>

      {/* Vignette so the centred text keeps its contrast wherever the field
          happens to be dense. */}
      <div
        aria-hidden
        className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(15,17,21,0.55)_0%,rgba(15,17,21,0.15)_45%,rgba(15,17,21,0.7)_100%)]"
      />

      <main className="page-enter relative flex h-full flex-col items-center justify-center gap-6 px-6 text-center">
        <h1 className="font-heading text-5xl font-medium tracking-tight sm:text-6xl">
          <ShinyText text="Investment OS" color="#b5b5b5" shineColor="#ffffff" speed={3} />
        </h1>

        <p className="max-w-xl text-base text-text-secondary">
          Remembers why you invested. Checks if it still holds.
        </p>

        <div className="mt-2">
          <SpecularButton onClick={() => navigate('/theses')}>
            Open dashboard
          </SpecularButton>
        </div>
      </main>
    </div>
  )
}
