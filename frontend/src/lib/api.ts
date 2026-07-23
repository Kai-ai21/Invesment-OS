const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000"

/* ---------------------------------------------------------------------------
 * Types — mirror backend/api/schemas.py. Datetimes arrive as ISO-8601 strings.
 * ------------------------------------------------------------------------- */

/** Claim statuses produced by backend/domain/status.py. */
export type ClaimStatus =
  | "strongly_supported"
  | "supported"
  | "weakening"
  | "broken"
  | "pending"

/** Thesis statuses produced by backend/domain/status.py. */
export type ThesisStatus = "strengthening" | "weakening" | "breaking" | "pending"

/** Verdict an LLM verification returns for one claim against one document. */
export type Verdict = "supports" | "contradicts" | "neutral"

/** ClaimOut */
export interface Claim {
  id: string
  statement: string
  proof_condition: string
  break_condition: string
  is_core: boolean
  status: ClaimStatus
}

/** ThesisOut */
export interface Thesis {
  id: string
  ticker: string
  reasoning_raw: string
  status: ThesisStatus
  created_at: string
  claims: Claim[]
}

/** EvidenceEventOut */
export interface EvidenceEvent {
  id: string
  claim_id: string
  document_id: string
  verdict: Verdict
  confidence: number
  evidence_quote: string
  reasoning: string
  created_at: string
}

/** AlertOut */
export interface Alert {
  id: string
  thesis_id: string
  /** Denormalised from the related thesis so the feed needn't fetch each one. */
  ticker: string
  prev_status: ThesisStatus
  new_status: ThesisStatus
  summary: string
  is_read: boolean
  created_at: string
}

/** CheckedFilingOut */
export interface CheckedFiling {
  title: string
  evidence_created: number
}

/** SkippedFilingOut */
export interface SkippedFiling {
  title: string
  reason: string
}

/** CheckResultOut */
export interface CheckResult {
  ticker: string
  filings_found: number
  checked: CheckedFiling[]
  skipped: SkippedFiling[]
  status_before: ThesisStatus
  status_after: ThesisStatus
  total_evidence_created: number
}

/* ---------------------------------------------------------------------------
 * Fetch helper
 * ------------------------------------------------------------------------- */

/**
 * FastAPI reports errors as `{"detail": ...}`. Pull that out so the UI can show
 * the backend's own wording instead of a wall of JSON; fall back to the raw body.
 */
function readableBody(body: string): string {
  try {
    const parsed: unknown = JSON.parse(body)
    if (parsed && typeof parsed === "object" && "detail" in parsed) {
      const { detail } = parsed as { detail: unknown }
      return typeof detail === "string" ? detail : JSON.stringify(detail)
    }
  } catch {
    // not JSON — fall through to the raw body
  }
  return body || "(empty response body)"
}

/** Thrown for any non-2xx response, carrying the status and the raw body. */
export class ApiError extends Error {
  readonly status: number
  readonly body: string
  readonly path: string

  constructor(status: number, body: string, path: string) {
    super(`${path} failed (${status}): ${readableBody(body)}`)
    this.name = "ApiError"
    this.status = status
    this.body = body
    this.path = path
  }

  /** Just the backend's message, without the path/status prefix. */
  get detail(): string {
    return readableBody(this.body)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...init?.headers,
      },
    })
  } catch (cause) {
    // fetch only rejects on network-level failure — usually the backend is down
    // or CORS blocked the request before a status was ever seen.
    throw new Error(
      `Could not reach the API at ${API_BASE}${path}. Is the backend running?`,
      { cause },
    )
  }

  if (!response.ok) {
    throw new ApiError(response.status, await response.text(), path)
  }

  return response.json() as Promise<T>
}

/* ---------------------------------------------------------------------------
 * Endpoints
 * ------------------------------------------------------------------------- */

export function listTheses(): Promise<Thesis[]> {
  return request<Thesis[]>("/theses")
}

export function getThesis(id: string): Promise<Thesis> {
  return request<Thesis>(`/theses/${encodeURIComponent(id)}`)
}

/**
 * Extract claims from free-text reasoning and persist the thesis.
 * Slow — the backend runs an LLM extraction, typically 5-15s.
 */
export function createThesis(ticker: string, reasoning: string): Promise<Thesis> {
  return request<Thesis>("/theses", {
    method: "POST",
    body: JSON.stringify({ ticker, reasoning }),
  })
}

export function listEvidence(thesisId: string): Promise<EvidenceEvent[]> {
  return request<EvidenceEvent[]>(
    `/theses/${encodeURIComponent(thesisId)}/evidence`,
  )
}

/**
 * Verify a pasted document against every claim on the thesis.
 * Slow — one LLM call per claim, typically 10-40s. Returns only the evidence
 * events that were created; an empty array means nothing in the document was
 * relevant, which is a normal outcome rather than a failure.
 */
export function submitDocument(
  thesisId: string,
  rawText: string,
  title?: string,
): Promise<EvidenceEvent[]> {
  return request<EvidenceEvent[]>(
    `/theses/${encodeURIComponent(thesisId)}/documents`,
    {
      method: "POST",
      body: JSON.stringify({ raw_text: rawText, title: title ?? null }),
    },
  )
}

/**
 * Pull recent SEC filings for the thesis's ticker and verify each one.
 * Very slow — `limit` filings x one LLM call per claim.
 */
export function runCheck(thesisId: string, limit = 1): Promise<CheckResult> {
  return request<CheckResult>(
    `/theses/${encodeURIComponent(thesisId)}/check?limit=${limit}`,
    { method: "POST" },
  )
}

export function listAlerts(unreadOnly = false): Promise<Alert[]> {
  const query = unreadOnly ? "?unread_only=true" : ""
  return request<Alert[]>(`/alerts${query}`)
}

/** Returns the updated alert, so callers can swap it in without a refetch. */
export function markAlertRead(alertId: string): Promise<Alert> {
  return request<Alert>(`/alerts/${encodeURIComponent(alertId)}/read`, {
    method: "PATCH",
  })
}
