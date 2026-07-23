import { useEffect, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { listTheses, type ClaimStatus, type Thesis, type ThesisStatus } from '@/lib/api'

/** Status → badge colour. Covers both thesis and claim statuses; text carries the
 *  meaning too, so colour is never the only signal. */
const STATUS_CLASSES: Record<ThesisStatus | ClaimStatus, string> = {
  strengthening: 'bg-status-strengthening/10 text-status-strengthening',
  strongly_supported: 'bg-status-supported/10 text-status-supported',
  supported: 'bg-status-supported/10 text-status-supported',
  weakening: 'bg-status-weakening/10 text-status-weakening',
  breaking: 'bg-status-breaking/10 text-status-breaking',
  broken: 'bg-status-broken/10 text-status-broken',
  pending: 'bg-status-pending/10 text-status-pending',
}

function StatusBadge({ status }: { status: ThesisStatus | ClaimStatus }) {
  return (
    <Badge className={STATUS_CLASSES[status] ?? STATUS_CLASSES.pending}>
      {status.replace(/_/g, ' ')}
    </Badge>
  )
}

function App() {
  const [theses, setTheses] = useState<Thesis[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    listTheses()
      .then((data) => {
        if (!cancelled) setTheses(data)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Theses</h1>

      {error !== null ? (
        <p className="text-status-broken" role="alert">
          {error}
        </p>
      ) : theses === null ? (
        <p className="text-text-secondary">Loading…</p>
      ) : theses.length === 0 ? (
        <p className="text-text-secondary">No theses yet.</p>
      ) : (
        <ul className="flex flex-col gap-4">
          {theses.map((thesis) => (
            <li key={thesis.id} className="rounded-lg border bg-surface p-4">
              <div className="flex items-center gap-3">
                <span className="font-medium">{thesis.ticker}</span>
                <StatusBadge status={thesis.status} />
              </div>

              <ul className="mt-3 flex flex-col gap-2">
                {thesis.claims.map((claim) => (
                  <li key={claim.id} className="flex items-start gap-3 text-sm">
                    <StatusBadge status={claim.status} />
                    <span className="text-text-secondary">{claim.statement}</span>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}

export default App
