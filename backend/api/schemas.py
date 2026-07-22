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
