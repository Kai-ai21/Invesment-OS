from pydantic import BaseModel, Field


class DocumentData(BaseModel):
    """A loaded document ready to be checked against claims."""

    source_type: str = Field(description="Where the document came from, e.g. 'paste'.")
    title: str | None = Field(description="Optional human-readable title.")
    content_hash: str = Field(description="sha256 hex digest of the raw text, used for dedup.")
    raw_text: str = Field(description="The full document text.")
