import { handleUnauthorized, readToken } from "@/lib/authToken"

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
  /** How much evidence this claim has been judged on. */
  evidence_count: number
  /**
   * The weighted score the status was derived from — supporting confidence minus
   * contradicting confidence — computed by backend/domain/status.py.
   *
   * ⚠️ NULL, NOT ZERO, when there is no evidence: 0.0 is a real score meaning
   * support and contradiction cancelled out, which is a different thing from
   * never having been looked at. Never recompute this client-side; the status
   * engine owns the maths and this is the number the status was decided on.
   */
  score: number | null
  /** [floor, ceiling] the score is read against, from the same module. Sent
   *  rather than hard-coded so a band change server-side cannot leave the bar
   *  describing the old scale. Real scores can fall OUTSIDE it. */
  score_scale: [number, number]
}

/** ThesisOut */
export interface Thesis {
  id: string
  ticker: string
  /** Derived server-side from a curated ticker->domain map. Null when unmapped —
   *  CompanyLogo falls back to the ticker's initials, which is the normal case. */
  logo_url: string | null
  reasoning_raw: string
  status: ThesisStatus
  created_at: string
  claims: Claim[]
  /**
   * Both DERIVED server-side from the evidence events, not stored on the thesis —
   * so they cannot drift from the events they describe. Denormalised onto the
   * thesis for the same reason AlertOut carries `ticker`: the list shows them on
   * every card, and fetching evidence per card to count it would be one request
   * per thesis.
   */
  evidence_count: number
  /** When the newest evidence landed, i.e. when this was last actually checked
   *  against anything. Null means never. */
  last_evidence_at: string | null
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

/** PostMortemOut */
export interface PostMortem {
  id: string
  thesis_id: string
  ticker: string
  /** See Thesis.logo_url. */
  logo_url: string | null
  /**
   * Null for a MANUALLY opened reflection — there is no specific broken claim, so
   * the UI shows a fixed question and never asks the AI for one.
   */
  broken_claim_id: string | null
  broken_claim_statement: string | null
  /** Written by the AI on demand; null until generateQuestion() has run. */
  prompt_question: string | null
  /** Null means still pending. This is the only pending/answered flag. */
  user_response: string | null
  status_at_break: ThesisStatus
  created_at: string
  answered_at: string | null
}

/** PatternSourceOut */
export interface PatternSource {
  post_mortem_id: string
  ticker: string
  prompt_question: string | null
}

/** PatternOut */
export interface Pattern {
  id: string
  statement: string
  /**
   * The reflections this observation is drawn from. Always at least two — the
   * backend rejects any pattern citing fewer, or citing an id it never supplied.
   * A source the user has since deleted drops out, so this can be shorter than
   * what the AI originally cited.
   */
  sources: PatternSource[]
  generated_at: string
  dismissed: boolean
}

/** PatternGenerateOut */
export interface PatternGenerateResult {
  patterns: Pattern[]
  /**
   * Populated only when `patterns` is empty, explaining WHY — "not enough
   * reflections yet" and "analysed and found nothing" are different messages to
   * show someone about their own judgement. Neither is an error.
   */
  reason: string | null
}

/** NewsItemOut */
export interface NewsItem {
  title: string
  url: string
  source: string
  /** The COMPANY's logo (from the ticker), distinct from favicon_url which is the
   *  news PUBLISHER's icon. Both can appear on one row. */
  logo_url: string | null
  /** Publisher domain, e.g. "barrons.com". Null when the feed gave no source URL. */
  source_domain: string | null
  /** Derived from source_domain. Null when there was no domain to derive it from. */
  favicon_url: string | null
  /**
   * Null when the feed omitted the date or gave one the backend could not parse.
   * Never guessed, so the UI must render "no date" rather than inventing one.
   */
  published_at: string | null
  ticker: string
}

/** ChartPricePointOut */
export interface ChartPricePoint {
  date: string
  close: number
}

/** ChartEventOut — one annotation. `type` discriminates the two shapes. */
export interface ChartEvent {
  date: string
  type: 'evidence' | 'status_change'
  // type === 'evidence'
  verdict: Verdict | null
  quote: string | null
  claim_statement: string | null
  confidence: number | null
  // type === 'status_change'
  prev_status: ThesisStatus | null
  new_status: ThesisStatus | null
}

/** ChartDataOut */
export interface ChartData {
  ticker: string
  prices: ChartPricePoint[]
  events: ChartEvent[]
  /** True when the price source failed. Events are still present — a broken upstream
   *  must never hide the user's own record, so the chart says so rather than drawing
   *  a flat line at zero. */
  prices_unavailable: boolean
}

/** HoldingOut — one position, with everything the backend derived for it. */
export interface Holding {
  id: string
  ticker: string
  /** See Thesis.logo_url. */
  logo_url: string | null
  shares: number
  /** Per share, not the total outlay. */
  average_cost: number
  purchased_at: string | null
  note: string | null
  created_at: string

  /**
   * ⚠️ EVERY ONE OF THESE IS null WHEN THE PRICE COULD NOT BE FETCHED — never 0.
   * The backend is explicit about this (backend/domain/portfolio.py) because a 0
   * renders as a real number and shows a healthy position as a total loss. The UI
   * must render "—" for a null, never fall back to 0, and never use `?? 0`.
   */
  current_price: number | null
  market_value: number | null
  unrealised_pnl: number | null
  pnl_percent: number | null
  allocation_percent: number | null
  /** The exception: what was PAID needs no live price and survives an outage. */
  cost_basis: number

  price_unavailable: boolean
  /**
   * WHY there is no price, as a value to BRANCH on. The two failures need different
   * things from the user (fix the symbol vs. wait), and telling them apart by
   * matching on `price_error`'s English would break the moment it was reworded.
   */
  price_status: 'ok' | 'unknown_ticker' | 'source_unavailable'
  /** The same thing in words, for display. Null when the price came back fine. */
  price_error: string | null

  /** Both null when the user owns something they never wrote a thesis about.
   *  That is normal, not a problem to flag. */
  thesis_id: string | null
  thesis_status: ThesisStatus | null
}

/** PortfolioTotalsOut — computed over the PRICED holdings only. */
export interface PortfolioTotals {
  market_value: number
  cost_basis: number
  unrealised_pnl: number
  /** Null on a zero cost basis — no denominator to be a percentage of. */
  pnl_percent: number | null
  holdings_counted: number
  /**
   * How many holdings these totals LEAVE OUT because their price was unavailable.
   * Non-zero means the totals are partial and the UI must say so — a total that
   * looks complete when it isn't is the failure mode this field exists to prevent.
   */
  holdings_excluded: number
}

/** PortfolioOut */
export interface Portfolio {
  holdings: Holding[]
  totals: PortfolioTotals
}

/** QuoteOut — one company on the market page. */
export interface Quote {
  ticker: string
  /** See Thesis.logo_url. */
  logo_url: string | null
  company_name: string | null
  /**
   * ⚠️ Null — never 0 — when the quote could not be fetched. A $0.00 price beside
   * a real company name reads as a catastrophe rather than a failed HTTP call, so
   * the UI renders "unavailable" and no call site may use `?? 0`.
   */
  price: number | null
  previous_close: number | null
  change: number | null
  change_percent: number | null
  market_cap: number | null
  /** True when this company's quote failed. The card still appears. */
  unavailable: boolean
  error: string | null
}

/** CompanyProfileOut. Every field is optional ON EVIDENCE — funds and trusts
 *  return no sector, industry, headcount, website or market cap. Absent means
 *  absent: render the row away, never "N/A" in a slot that looks like a fact. */
export interface CompanyProfile {
  name: string | null
  sector: string | null
  industry: string | null
  employees: number | null
  website: string | null
  long_business_summary: string | null
  market_cap: number | null
  price: number | null
  previous_close: number | null
  change: number | null
  change_percent: number | null
}

/** ResearchSummaryOut — the filing restated. A null field means the retrieved
 *  passages did not cover it, so the UI drops that card rather than showing a
 *  guess. Never contains an assessment; see backend/domain/research.py. */
export interface ResearchSummary {
  what_the_company_does: string | null
  how_it_makes_money: string | null
  key_risks: string[]
}

/** ResearchOut */
export interface Research {
  ticker: string
  logo_url: string | null
  profile: CompanyProfile | null
  summary: ResearchSummary | null
  /** Which document the summary came from — this is what makes the page credible
   *  rather than generic, so it is shown whenever a summary is. */
  source_filing_title: string | null
  source_filing_date: string | null
  source_filing_url: string | null
  /** True when the profile loaded but the filing summary didn't. NOT an error —
   *  the page renders the profile with a quiet note. */
  filing_summary_unavailable: boolean
  filing_summary_error: string | null
}

/** FilingOut — one SEC filing as EDGAR lists it. */
export interface Filing {
  /** "10-K" | "10-Q" | "8-K" as the SEC reports it. Kept a plain string: the form
   *  vocabulary is the SEC's, not ours, and a union here would break on an
   *  amendment (10-K/A) rather than just rendering it. */
  form: string
  /** ISO date, e.g. "2026-02-26". */
  filing_date: string
  title: string
  url: string
  /** The SEC's own id for the filing. Stable and unique, so it keys both the
   *  backend's 30-day summary cache and the client's expand-in-place state. */
  accession_number: string
}

/** NotableNumberOut — a figure paired with what it is a figure OF. */
export interface NotableNumber {
  figure: string
  what_it_measures: string
}

/**
 * RelevantClaimOut — a claim of the user's that a filing DISCUSSES.
 *
 * ⚠️ NOT a claim it supports. There is no verdict or confidence here and there must
 * never be one: that is an EvidenceEvent, produced by a different pipeline which
 * quotes the document verbatim and has its quote validated. Every id has already
 * been checked server-side against the user's real claims for this ticker.
 */
export interface RelevantClaim {
  claim_id: string
  thesis_id: string
  statement: string
}

/**
 * FilingSummaryOut — one filing restated in plain language.
 *
 * ⚠️ READING, NOT EVIDENCE. Nothing here was checked against anything, nothing was
 * scored, and producing it wrote nothing to the evidence log or to any status. The
 * shape has no field a verdict could go in, and the UI must keep the two visibly
 * apart — see FilingsSection.
 */
export interface FilingSummary {
  ticker: string
  filing: Filing
  /** One sentence on what this KIND of filing is for. */
  filing_type_explained: string
  key_points: string[]
  notable_numbers: NotableNumber[]
  /** EMPTY IS THE EXPECTED ANSWER most of the time. Say so plainly rather than
   *  rendering it as a failure. */
  relevance: RelevantClaim[]
}

/** EnhanceReasoningOut — a CANDIDATE rewrite, never applied automatically. */
export interface EnhancedReasoning {
  enhanced: string
  /** True when the model handed the input back because it could not sharpen it
   *  without inventing. Say "already specific enough" rather than pretending an
   *  edit happened. Computed backend-side on normalised whitespace, so a re-flowed
   *  line break does not read as a change. */
  unchanged: boolean
}

/** TickerMatchOut — one autocomplete suggestion. */
export interface TickerMatch {
  ticker: string
  company_name: string
}

/** HoldingCreateRequest. The backend uppercases the ticker and rejects
 *  shares <= 0 or average_cost < 0 with a 422. */
export interface HoldingCreate {
  ticker: string
  shares: number
  average_cost: number
  /** ISO date (YYYY-MM-DD), or null when the user didn't record one. */
  purchased_at?: string | null
  note?: string | null
}

/** HoldingUpdateRequest. An omitted key is left alone; an explicit null on `note`
 *  clears it, which is how a note gets deleted. */
export interface HoldingUpdate {
  shares?: number
  average_cost?: number
  note?: string | null
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

/**
 * Thrown when the request never reached the backend at all — the process is down,
 * the machine is offline, or CORS rejected it before a status existed.
 *
 * A DISTINCT CLASS, not a plain Error, because that is the only way the copy layer
 * can tell "we could not reach the server" (worth retrying, and the user's own
 * connection may be the cause) apart from a genuine bug in our own code, which
 * also surfaces as a plain Error and must not be described as a network problem.
 */
export class NetworkError extends Error {
  readonly path: string

  constructor(path: string, options?: { cause?: unknown }) {
    super(`Could not reach the API at ${API_BASE}${path}`, options)
    this.name = 'NetworkError'
    this.path = path
  }
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

/**
 * ⚠️ THE ONE PLACE THE TOKEN IS ATTACHED, AND THE ONE PLACE A 401 IS HANDLED.
 *
 * Every endpoint function below goes through here, so authentication is a property
 * of the transport rather than something each of the ~30 callers has to remember.
 * Adding an endpoint gets it for free; forgetting is not possible.
 *
 * `skipAuth` exists for exactly the two routes that must NOT send a token — signup
 * and login — because sending a stale one there would make a 401 from the global
 * handler fire during the very act of logging in.
 */
async function request<T>(
  path: string,
  init?: RequestInit & { skipAuth?: boolean },
): Promise<T> {
  const { skipAuth, ...requestInit } = init ?? {}
  const token = skipAuth ? null : readToken()

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...requestInit,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...requestInit.headers,
      },
    })
  } catch (cause) {
    // fetch only rejects on network-level failure — usually the backend is down
    // or CORS blocked the request before a status was ever seen.
    throw new NetworkError(path, { cause })
  }

  if (response.status === 401 && !skipAuth) {
    // ⚠️ HANDLED GLOBALLY, HERE, RATHER THAN AT ~30 CALL SITES. A token expires
    // while the app is open — mid-session, on whatever page the user happens to be
    // on — and every one of them would otherwise surface "Error: 401", which tells
    // the user nothing and offers them nothing to do.
    //
    // The token is cleared and the app is told; AuthContext turns that into a
    // redirect to /login carrying SESSION_EXPIRED_MESSAGE. The error is still
    // thrown, so the caller's own error handling still runs and no request
    // resolves with a value it never received.
    handleUnauthorized()
    throw new ApiError(401, await response.text(), path)
  }

  if (!response.ok) {
    throw new ApiError(response.status, await response.text(), path)
  }

  // 204 carries no body, so parsing it as JSON would throw on a successful call.
  // DELETE endpoints use it.
  if (response.status === 204) {
    return undefined as T
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

/**
 * Headlines across every ticker the user holds a thesis on, newest first.
 * The backend caches for 15 minutes and isolates per-ticker feed failures, so a
 * dead feed drops that ticker rather than failing the request.
 */
export function listNews(limitPerTicker = 5): Promise<NewsItem[]> {
  return request<NewsItem[]>(`/news?limit_per_ticker=${limitPerTicker}`)
}

/**
 * Headlines for ONE ticker, newest first — the same feed and the same 15-minute
 * cache the portfolio-wide call goes through, not a second source. Works for any
 * symbol, including one the user has never written a thesis about.
 *
 * ⚠️ AN EMPTY ARRAY IS A REAL ANSWER, not a failure: nobody published about this
 * symbol recently. Callers render an empty section, never an error. Rejects with
 * 404 only when the string could not be a ticker at all, and 502 when the feed
 * itself was unreachable.
 */
export function getNewsForTicker(ticker: string, limit = 10): Promise<NewsItem[]> {
  return request<NewsItem[]>(`/news/${encodeURIComponent(ticker)}?limit=${limit}`)
}

/* --- post-mortems --------------------------------------------------------- */

export function listPostMortems(pendingOnly = false): Promise<PostMortem[]> {
  const query = pendingOnly ? "?pending_only=true" : ""
  return request<PostMortem[]>(`/post-mortems${query}`)
}

export function listPostMortemsForThesis(thesisId: string): Promise<PostMortem[]> {
  return request<PostMortem[]>(
    `/theses/${encodeURIComponent(thesisId)}/post-mortems`,
  )
}

/**
 * Write the AI reflection question. Idempotent on the backend — an existing
 * question is returned untouched — so re-displaying a post-mortem costs nothing and
 * the wording never shifts under the user.
 *
 * Only for AUTOMATIC post-mortems. One with a null broken_claim_id has nothing
 * specific to ask about and the backend answers 422; the UI shows a fixed question
 * for those instead of calling this.
 */
export function generateQuestion(postMortemId: string): Promise<PostMortem> {
  return request<PostMortem>(
    `/post-mortems/${encodeURIComponent(postMortemId)}/question`,
    { method: "POST" },
  )
}

/** Returns the updated post-mortem, so callers can swap it in without a refetch. */
export function answerPostMortem(
  postMortemId: string,
  userResponse: string,
): Promise<PostMortem> {
  return request<PostMortem>(
    `/post-mortems/${encodeURIComponent(postMortemId)}`,
    { method: "PATCH", body: JSON.stringify({ user_response: userResponse }) },
  )
}

/** Post-mortems are deletable by design — unlike evidence, a reflection is the
 *  user's private note about themselves. Resolves with nothing (HTTP 204). */
export function deletePostMortem(postMortemId: string): Promise<void> {
  return request<void>(`/post-mortems/${encodeURIComponent(postMortemId)}`, {
    method: "DELETE",
  })
}

/** Open a reflection on demand, without waiting for the thesis to break. */
export function createManualPostMortem(thesisId: string): Promise<PostMortem> {
  return request<PostMortem>(
    `/theses/${encodeURIComponent(thesisId)}/post-mortems`,
    { method: "POST" },
  )
}

/* --- patterns ------------------------------------------------------------- */

/** The stored pattern set. Dismissed patterns are excluded by the backend. */
export function listPatterns(): Promise<Pattern[]> {
  return request<Pattern[]>("/patterns")
}

/**
 * Rebuild the pattern set from every answered reflection. Slow — one LLM call over
 * all of them. REPLACES the previous set rather than adding to it, so a pattern that
 * no longer holds disappears.
 */
export function generatePatterns(): Promise<PatternGenerateResult> {
  return request<PatternGenerateResult>("/patterns/generate", { method: "POST" })
}

/** Returns the updated pattern, so callers can drop it without a refetch. */
export function dismissPattern(patternId: string): Promise<Pattern> {
  return request<Pattern>(
    `/patterns/${encodeURIComponent(patternId)}/dismiss`,
    { method: "PATCH" },
  )
}

/** Prices for a thesis's ticker, annotated with its evidence and status changes. */
export function getChartData(thesisId: string, days = 365): Promise<ChartData> {
  return request<ChartData>(
    `/theses/${encodeURIComponent(thesisId)}/chart?days=${days}`,
  )
}

/** PriceHistoryOut — bare daily closes for a TICKER, with no thesis involved. */
export interface PriceHistory {
  ticker: string
  points: Array<{ date: string; close: number }>
}

/**
 * Daily closes for a ticker.
 *
 * Distinct from getChartData, which is thesis-scoped and carries the evidence
 * annotations the detail chart draws. A sparkline on a market card has no thesis
 * to hang off, so it reads the ticker endpoint — which is the same price service,
 * behind the same cache, not a second source.
 *
 * 404s when the ticker has no history at all; see lib/priceHistory for the
 * deduplicating cache every sparkline actually goes through.
 */
export function getPriceHistory(ticker: string, days = 30): Promise<PriceHistory> {
  return request<PriceHistory>(
    `/prices/${encodeURIComponent(ticker)}/history?days=${days}`,
  )
}

/* --- holdings ------------------------------------------------------------- */

/**
 * The whole portfolio: every holding with its computed values, plus totals.
 * Never fails on a price outage — a failed ticker is flagged on its own row and
 * excluded from the totals, so one bad symbol cannot blank the page.
 */
export function listHoldings(): Promise<Portfolio> {
  return request<Portfolio>('/holdings')
}

/**
 * The three mutations all resolve with the WHOLE portfolio rather than the single
 * row they touched, because adding, editing or removing a position changes every
 * other row's allocation percentage. Callers swap in the returned portfolio; there
 * is nothing to refetch.
 */
export function createHolding(fields: HoldingCreate): Promise<Portfolio> {
  return request<Portfolio>('/holdings', {
    method: 'POST',
    body: JSON.stringify(fields),
  })
}

export function updateHolding(id: string, fields: HoldingUpdate): Promise<Portfolio> {
  return request<Portfolio>(`/holdings/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    // Sent as given: an omitted key must stay omitted, since the backend uses the
    // presence of `note` to tell "leave it alone" from "clear it".
    body: JSON.stringify(fields),
  })
}

/** Resolves with nothing (HTTP 204). The caller refetches for new allocations. */
export function deleteHolding(id: string): Promise<void> {
  return request<void>(`/holdings/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

/* --- market --------------------------------------------------------------- */

/**
 * The twelve curated market leaders, ranked by LIVE market cap.
 *
 * Membership is hand-maintained on the backend and can go stale; the quotes and
 * the ranking are live. Always resolves with all twelve — a company whose quote
 * failed comes back flagged rather than missing, so a fetch failure can never be
 * mistaken for a company leaving the ranking. Never rejects on a single bad
 * ticker; the backend isolates those per company.
 */
export function listMarketLeaders(): Promise<Quote[]> {
  return request<Quote[]>('/market/leaders')
}

/* --- research ------------------------------------------------------------- */

/**
 * Company profile plus a plain-language summary of the latest SEC filing.
 *
 * ⚠️ SLOW on a cold cache — a filing fetch, two retrieval passes and one AI call,
 * so 10-20 seconds is normal and the UI must say what it is doing rather than
 * showing a bare spinner. Cached server-side per ticker for 24 hours.
 *
 * 404 means no such ticker; 502 means every upstream failed. A filing that could
 * not be read is NEITHER — it resolves normally with the profile and
 * `filing_summary_unavailable` set, so this rejecting always means the page has
 * nothing at all to show.
 */
export function getResearch(ticker: string): Promise<Research> {
  return request<Research>(`/research/${encodeURIComponent(ticker)}`)
}

/* --- filings -------------------------------------------------------------- */

/**
 * Recent 10-K, 10-Q and 8-K filings for one ticker, newest first.
 *
 * Fast — the SEC's index, cached server-side for six hours. AN EMPTY ARRAY IS A
 * NORMAL ANSWER: a real company that has filed none of these three forms. 404
 * means the SEC lists no such symbol; 502 means the SEC was unreachable, which is
 * "we could not look" rather than "there is nothing to see".
 */
export function listFilings(ticker: string, limit = 10): Promise<Filing[]> {
  return request<Filing[]>(
    `/filings/${encodeURIComponent(ticker)}?limit=${limit}`,
  )
}

/**
 * One filing, restated in plain language.
 *
 * ⚠️ READ-ONLY. This creates no evidence, moves no claim or thesis status and
 * writes nothing — unlike checkThesis, which does all three. A summary is
 * unverified reading; evidence is quoted, scored and validated.
 *
 * ⚠️ SLOW on a cold cache — a filing fetch, two retrieval passes and one AI call,
 * so 10-20 seconds is normal and the UI must say what it is doing rather than
 * showing a bare spinner. Cached server-side for 30 days per filing, since a
 * filing's contents are fixed the moment it is filed.
 *
 * `url` must be one the SEC actually lists for this ticker — the backend checks it
 * against the SEC's own index before fetching anything, so pass a URL that came
 * from listFilings rather than one built by hand. 404 otherwise.
 */
export function summariseFiling(
  ticker: string,
  filing: Filing,
): Promise<FilingSummary> {
  return request<FilingSummary>('/filings/summarise', {
    method: 'POST',
    // `title` is sent for the backend's convenience only — it is NOT trusted, and
    // the response's title, form and date all come from the SEC's own record.
    body: JSON.stringify({ ticker, url: filing.url, title: filing.title }),
  })
}

/* --- ticker autocomplete -------------------------------------------------- */

/**
 * Ticker suggestions from the SEC's company list (~10k rows, cached in the
 * backend process, so this is a plain in-process filter rather than a lookup).
 *
 * An EMPTY array is a normal answer — a short query, or a symbol the SEC does not
 * list. It is never a reason to block: the caller shows "no match, you can still
 * submit". A REJECTION means the SEC map itself is unreachable, and the caller
 * must fall back to a plain text field rather than surfacing an error, since
 * autocomplete failing should never stop someone writing a thesis.
 */
/**
 * Sharpen the user's own reasoning. Returns a CANDIDATE — nothing is stored and
 * nothing is overwritten; the caller shows it beside the original and the user
 * picks. Slow (an AI call, a few seconds). 422 when the text is too thin to
 * sharpen without inventing.
 *
 * ⚠️ ENTIRELY OPTIONAL. createThesis never calls this, and a failure here must
 * stay inline — the form submits with or without it.
 */
export function enhanceReasoning(
  ticker: string,
  reasoning: string,
): Promise<EnhancedReasoning> {
  return request<EnhancedReasoning>('/theses/enhance-reasoning', {
    method: 'POST',
    body: JSON.stringify({ ticker, reasoning }),
  })
}

export function searchTickers(query: string, limit = 8): Promise<TickerMatch[]> {
  return request<TickerMatch[]>(
    `/tickers/search?q=${encodeURIComponent(query)}&limit=${limit}`,
  )
}

/* ---------------------------------------------------------------------------
 * Auth
 * ------------------------------------------------------------------------- */

/** UserOut. Deliberately never carries password_hash — see backend/api/schemas.py. */
export interface User {
  id: string
  email: string
}

/** TokenResponse */
export interface AuthToken {
  access_token: string
  token_type: string
}

/**
 * ⚠️ BOTH OF THESE PASS skipAuth. They are the two routes the backend leaves
 * public, and they are the only two that must not carry an Authorization header:
 * a stale token sent here would trip the global 401 handler in `request` and fire
 * a "session expired" redirect in the middle of someone logging in.
 */
export function signup(email: string, password: string): Promise<AuthToken> {
  return request<AuthToken>('/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
    skipAuth: true,
  })
}

export function login(email: string, password: string): Promise<AuthToken> {
  return request<AuthToken>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
    skipAuth: true,
  })
}

/**
 * Who the stored token belongs to. This is the token VALIDATION call: the backend
 * checks signature, expiry and that the account still exists, so a 401 here is the
 * definitive answer that a stored token is no longer usable.
 */
export function getMe(): Promise<User> {
  return request<User>('/auth/me')
}
