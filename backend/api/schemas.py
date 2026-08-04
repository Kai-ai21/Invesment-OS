from datetime import date as DateOnly, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
)

from backend.core.security import MAX_PASSWORD_BYTES
from backend.domain.company_domains import logo_url_for_ticker
from backend.domain.status import CLAIM_SCORE_SCALE


class TickerLogoMixin(BaseModel):
    """Adds a DERIVED logo_url to any response carrying a ticker.

    Computed on the way out rather than stored: the mapping is static code, so
    persisting it would just be a copy that can go stale. None when the ticker is not
    in the curated map — the UI falls back to its initials.
    """

    ticker: str

    @computed_field
    @property
    def logo_url(self) -> str | None:
        return logo_url_for_ticker(self.ticker)


class ThesisCreateRequest(BaseModel):
    ticker: str
    reasoning: str


class ClaimOut(BaseModel):
    id: str
    statement: str
    proof_condition: str
    break_condition: str
    is_core: bool
    status: str

    # How much evidence this claim has been judged on.
    evidence_count: int = 0

    # The weighted score the status was derived from: supporting confidence minus
    # contradicting confidence, straight out of domain/status.py.
    #
    # ⚠️ NULL, NOT ZERO, when there is no evidence. Zero is a real score meaning
    # "support and contradiction cancelled out" — a claim that has been examined
    # and found balanced. A pending claim has not been examined at all, and
    # showing it as 0.0 would put it on the bar next to genuinely contested
    # claims. Same rule as the money formatters: an absent number is never a zero.
    score: float | None = None

    # The two ends of the range `score` is read against, so the bar drawn from it
    # never hard-codes a threshold this service could change. Both come from
    # domain/status.py.
    score_scale: tuple[float, float] = CLAIM_SCORE_SCALE

    model_config = {"from_attributes": True}


class ThesisOut(TickerLogoMixin):
    id: str
    reasoning_raw: str
    status: str
    created_at: datetime
    claims: list[ClaimOut]

    # Denormalised onto the thesis for the same reason AlertOut carries `ticker`:
    # the list view shows both on every card, and fetching evidence per card to
    # count it would be one request per thesis. Defaulted so a caller that has not
    # attached a summary still validates — an unknown count reads as none, which is
    # also what a brand-new thesis has.
    evidence_count: int = 0
    # When the newest evidence event landed, i.e. when this thesis was last
    # actually checked against anything. None means never.
    last_evidence_at: datetime | None = None

    model_config = {"from_attributes": True}


class DocumentSubmitRequest(BaseModel):
    raw_text: str
    title: str | None = None


class EvidenceEventOut(BaseModel):
    id: str
    claim_id: str
    document_id: str
    verdict: str
    confidence: float
    evidence_quote: str
    reasoning: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckedFilingOut(BaseModel):
    title: str
    evidence_created: int


class SkippedFilingOut(BaseModel):
    title: str
    reason: str


class CheckResultOut(BaseModel):
    ticker: str
    filings_found: int
    checked: list[CheckedFilingOut]
    skipped: list[SkippedFilingOut]
    status_before: str
    status_after: str
    total_evidence_created: int


class AlertOut(BaseModel):
    id: str
    thesis_id: str
    ticker: str  # read from the related thesis via Alert.ticker
    prev_status: str
    new_status: str
    summary: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PostMortemOut(TickerLogoMixin):
    id: str
    thesis_id: str
    # `ticker` comes from TickerLogoMixin; the ORM supplies it via PostMortem.ticker.
    broken_claim_id: str | None
    # Denormalised from the related claim so the frontend needn't fetch it separately.
    broken_claim_statement: str | None
    prompt_question: str | None  # written by the AI in Step 2; null until then
    user_response: str | None  # null means still pending
    status_at_break: str
    created_at: datetime
    answered_at: datetime | None

    model_config = {"from_attributes": True}


class PostMortemAnswerRequest(BaseModel):
    user_response: str


class PatternSourceOut(BaseModel):
    """One reflection a pattern is drawn from, resolved so the frontend can show what
    the observation is based on without fetching each post-mortem."""

    post_mortem_id: str
    ticker: str
    prompt_question: str | None


class PatternOut(BaseModel):
    id: str
    statement: str
    sources: list[PatternSourceOut]
    generated_at: datetime
    dismissed: bool


class PatternGenerateOut(BaseModel):
    """Regeneration result.

    `reason` is populated when the set came back empty, so the UI can distinguish "not
    enough reflections yet" from "analysed them and found nothing" — two very different
    messages to show someone. Neither is an error.
    """

    patterns: list[PatternOut]
    reason: str | None = None


class NewsItemOut(TickerLogoMixin):
    title: str
    url: str
    source: str
    # Both None when the feed gave no usable source URL — never derived from the
    # publisher's name, which would produce a confidently wrong icon.
    source_domain: str | None
    favicon_url: str | None
    # None when the feed omitted the date or gave one we could not parse — never
    # guessed, so the frontend can show "no date" rather than a wrong one.
    published_at: datetime | None
    ticker: str

    model_config = {"from_attributes": True}


class PricePointOut(BaseModel):
    # Aliased: a field NAMED `date` would shadow a bare `date` import in its own
    # annotation, which pydantic cannot resolve.
    date: DateOnly
    close: float
    # Populated only on a current price — a history row has no "previous" to compare
    # against, and a zero would read as "flat" rather than "not applicable".
    previous_close: float | None = None
    change: float | None = None
    change_percent: float | None = None

    model_config = {"from_attributes": True}


class PriceHistoryOut(BaseModel):
    ticker: str
    points: list[PricePointOut]


class ChartPricePointOut(BaseModel):
    """Deliberately leaner than PricePointOut: a chart needs date and close, and the
    change fields would be dead weight repeated across a year of rows."""

    date: DateOnly
    close: float


class ChartEventOut(BaseModel):
    """One annotation on the chart. `type` discriminates the two shapes — evidence
    fields are null on a status change and vice versa, rather than two parallel arrays
    the frontend would have to merge and re-sort itself."""

    date: DateOnly
    type: str  # "evidence" | "status_change"

    # type == "evidence"
    verdict: str | None = None
    quote: str | None = None
    claim_statement: str | None = None
    confidence: float | None = None

    # type == "status_change"
    prev_status: str | None = None
    new_status: str | None = None


class ChartDataOut(BaseModel):
    ticker: str
    prices: list[ChartPricePointOut]
    events: list[ChartEventOut]
    # True when the price source failed. The events are still returned, so a broken
    # upstream cannot hide the user's own evidence — the chart shows "price data
    # unavailable" instead of a flat line at zero.
    prices_unavailable: bool = False


class QuoteOut(TickerLogoMixin):
    """One company on the market page.

    Every numeric field is null — never 0 — when the quote could not be fetched, so
    a failed request can never render as a company priced at nothing. `ticker` and
    `logo_url` come from TickerLogoMixin.
    """

    company_name: str | None
    price: float | None
    previous_close: float | None
    change: float | None
    change_percent: float | None
    market_cap: float | None
    unavailable: bool
    error: str | None

    model_config = {"from_attributes": True}


class CompanyProfileOut(BaseModel):
    """Descriptive detail. Every field but the ticker is optional ON EVIDENCE — funds
    and trusts return no sector, industry, headcount, website or market cap. Absent
    means absent: the UI omits the row rather than printing "N/A"."""

    name: str | None
    sector: str | None
    industry: str | None
    employees: int | None
    website: str | None
    long_business_summary: str | None
    market_cap: float | None
    price: float | None
    previous_close: float | None
    change: float | None
    change_percent: float | None

    model_config = {"from_attributes": True}


class ResearchSummaryOut(BaseModel):
    """The filing, restated. Null fields mean the retrieved passages did not cover
    that subject — the UI drops the card rather than showing a guess."""

    what_the_company_does: str | None
    how_it_makes_money: str | None
    key_risks: list[str]

    model_config = {"from_attributes": True}


class ResearchOut(TickerLogoMixin):
    """`ticker` and `logo_url` come from TickerLogoMixin."""

    profile: CompanyProfileOut | None
    summary: ResearchSummaryOut | None

    # Which document the summary came from. This is what separates the page from a
    # generic description, so it is always shown when a summary is.
    source_filing_title: str | None
    source_filing_date: str | None
    source_filing_url: str | None

    # True when the profile loaded but the filing summary did not. NOT an error: the
    # page renders with the profile and a quiet note.
    filing_summary_unavailable: bool
    filing_summary_error: str | None

    model_config = {"from_attributes": True}


class FilingOut(BaseModel):
    """One SEC filing as EDGAR lists it. A row to browse, not a document we read."""

    form: str
    filing_date: str
    title: str
    url: str
    accession_number: str

    model_config = {"from_attributes": True}


class FilingSummariseRequest(BaseModel):
    """⚠️ `title` is accepted for the client's convenience and is NOT trusted.

    The response's title, form and date all come from the SEC's own record of the
    filing at `url`, resolved server-side — a caller could otherwise label a 10-K as
    an 8-K, and the one thing a summary must get right is which document it is of.
    The URL itself is checked against the filings the SEC lists for this ticker
    before anything is fetched; see filing_service.LOOKUP_LIMIT.
    """

    ticker: str
    url: str
    title: str | None = None


class NotableNumberOut(BaseModel):
    """A figure and what it measures. Paired because a figure alone makes the reader
    guess what it is of, and a guessed meaning is worse than no number."""

    figure: str
    what_it_measures: str

    model_config = {"from_attributes": True}


class RelevantClaimOut(BaseModel):
    """A claim of the user's that this filing DISCUSSES.

    ⚠️ Not a claim it supports. There is no verdict, confidence or direction here and
    there must never be one — that is an EvidenceEventOut, which is produced by a
    different pipeline, quotes the document verbatim, and has its quote validated.
    """

    claim_id: str
    thesis_id: str
    statement: str

    model_config = {"from_attributes": True}


class FilingSummaryOut(BaseModel):
    """One filing, restated in plain language. READING, NOT EVIDENCE.

    Deliberately shaped so it cannot be mistaken for one: no verdict, no confidence,
    no status, and nothing this produces is ever written to the evidence log.
    """

    ticker: str
    filing: FilingOut

    filing_type_explained: str
    key_points: list[str]
    notable_numbers: list[NotableNumberOut]
    # Empty is the expected answer most of the time. Every id here has been checked
    # against the user's real claims for this ticker; see filing_service.
    relevance: list[RelevantClaimOut]

    model_config = {"from_attributes": True}


class EnhanceReasoningRequest(BaseModel):
    ticker: str
    reasoning: str


class EnhanceReasoningOut(BaseModel):
    """A CANDIDATE rewrite — never applied automatically. The frontend shows it
    beside the original and the user picks."""

    enhanced: str
    # True when the model returned the input as-is because it could not sharpen it
    # without inventing. The UI says "already specific enough" rather than
    # pretending an edit happened.
    unchanged: bool


class TickerMatchOut(BaseModel):
    """One autocomplete suggestion. No CIK: the frontend has no use for it, and an
    autocomplete response is not the place to hand out internal identifiers."""

    ticker: str
    company_name: str

    model_config = {"from_attributes": True}


class HoldingCreateRequest(BaseModel):
    ticker: str
    # Constrained here rather than in the route: pydantic turns a violation into
    # FastAPI's own 422 with the offending field named, which is a better error than
    # anything hand-rolled would produce.
    shares: float = Field(gt=0)
    # >= 0, not > 0: shares can genuinely cost nothing (a grant, a spin-off).
    average_cost: float = Field(ge=0)
    purchased_at: DateOnly | None = None
    note: str | None = None

    @field_validator("ticker")
    @classmethod
    def _normalise_ticker(cls, value: str) -> str:
        """Uppercase and non-empty.

        Lowercase input is NORMALISED, not rejected — "nvda" is unambiguous and
        bouncing it would be pedantry. Whitespace-only is rejected, because there is
        nothing to normalise it into.
        """
        ticker = value.strip().upper()
        if not ticker:
            raise ValueError("Ticker must not be empty")
        return ticker


class HoldingUpdateRequest(BaseModel):
    """Partial update. An omitted field is left alone; see the note in
    holding_repository.update_holding about why `note` needs the distinction."""

    shares: float | None = Field(default=None, gt=0)
    average_cost: float | None = Field(default=None, ge=0)
    note: str | None = None


class HoldingOut(TickerLogoMixin):
    id: str
    # `ticker` and `logo_url` come from TickerLogoMixin.
    shares: float
    average_cost: float
    purchased_at: DateOnly | None
    note: str | None
    created_at: datetime

    # Every one of these is None when the price could not be fetched — never 0. The
    # reasoning is in backend/domain/portfolio.py; the short version is that 0 would
    # render a healthy position as a total loss.
    current_price: float | None
    market_value: float | None
    unrealised_pnl: float | None
    pnl_percent: float | None
    allocation_percent: float | None
    # The exception: what was paid needs no live price and survives an outage.
    cost_basis: float

    price_unavailable: bool
    # WHY there is no price, as a value to branch on: "ok" | "unknown_ticker" |
    # "source_unavailable". The two failures need different things from the user
    # (fix the symbol vs. wait), and a UI telling them apart by matching on English
    # prose would break the moment the wording changed.
    price_status: str
    # The same thing in words, for display. Null when the price came back fine.
    price_error: str | None

    # Null when the user owns something they never wrote a thesis about. Normal.
    thesis_id: str | None
    thesis_status: str | None


class PortfolioTotalsOut(BaseModel):
    """Totals over the PRICED holdings only.

    `holdings_excluded` is what keeps this honest: it says how many positions these
    figures leave out, so a partial total is visibly partial instead of quietly wrong.
    """

    market_value: float
    cost_basis: float
    unrealised_pnl: float
    pnl_percent: float | None  # None on a zero cost basis
    holdings_counted: int
    holdings_excluded: int


class PortfolioOut(BaseModel):
    holdings: list[HoldingOut]
    totals: PortfolioTotalsOut


# --- auth -------------------------------------------------------------------------


def _normalise_email(value: str) -> str:
    """Trim and lowercase. Applied on the way IN, so storage and lookup agree.

    ⚠️ NORMALISING ON WRITE IS WHAT MAKES THE UNIQUE CONSTRAINT MEAN ANYTHING.
    "Ada@Example.com " and "ada@example.com" are the same mailbox; stored raw, the
    database sees two distinct strings and happily creates two accounts for one
    person, and whichever one they land in at login is down to how they typed it.
    """
    return value.strip().lower()


class SignupRequest(BaseModel):
    # EmailStr rather than str: format is checked here, so the route never has to,
    # and a malformed address is a 422 from the schema rather than a hand-written
    # branch. `mode="before"` so the trim/lowercase happens FIRST — otherwise a
    # trailing space fails validation before it can be stripped.
    email: EmailStr
    # 8 characters is the floor the brief set. The MAXIMUM is not a policy: bcrypt
    # cannot hash more than 72 BYTES and raises above that, so an over-long password
    # would 500 on the way to the hasher. Checked in bytes by the validator below,
    # because max_length counts characters and the two differ for anything non-ASCII.
    password: str = Field(min_length=8)

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return _normalise_email(value) if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        encoded = value.encode("utf-8")
        if len(encoded) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Password must be at most {MAX_PASSWORD_BYTES} bytes "
                f"({len(encoded)} given; note that accented and non-Latin characters "
                "take more than one byte each)."
            )
        return value


class LoginRequest(BaseModel):
    """⚠️ `email` IS A PLAIN str HERE, NOT EmailStr, AND THAT IS DELIBERATE.

    Login must answer identically for every failure. If this field validated the
    address format, a malformed email would come back 422 while an unknown-but-valid
    one came back 401 — a difference an attacker can read. Everything that is not the
    right password for an existing account gets the same 401 and the same sentence.

    The password has no length rules either, for the same reason: rejecting a
    7-character attempt at the schema would say "that is not even long enough to be
    one of our passwords", which is a fact about our policy, but the 422/401 split
    also tells them the request never reached the account lookup.
    """

    email: str
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return _normalise_email(value) if isinstance(value, str) else value


class TokenResponse(BaseModel):
    access_token: str
    # "bearer" is what the OAuth2 spec calls this and what the Authorization header
    # must say. Constant for now; it stays a field because clients are expected to
    # read it rather than hard-code the word.
    token_type: str = "bearer"


class UserOut(BaseModel):
    """The public shape of a user.

    ⚠️ THE ABSENCE OF password_hash IS THE ENTIRE JOB OF THIS CLASS. It is an
    explicit allow-list, not a copy of the model with one field removed: a field
    added to User later does not appear here until somebody adds it on purpose, so
    the next secret to land on that table is not published by default.
    """

    id: str
    email: str

    model_config = ConfigDict(from_attributes=True)
