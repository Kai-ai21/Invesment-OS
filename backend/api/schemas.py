from datetime import datetime

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}


class ThesisOut(BaseModel):
    id: str
    ticker: str
    reasoning_raw: str
    status: str
    created_at: datetime
    claims: list[ClaimOut]

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


class PostMortemOut(BaseModel):
    id: str
    thesis_id: str
    ticker: str  # read from the related thesis via PostMortem.ticker
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


class NewsItemOut(BaseModel):
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
