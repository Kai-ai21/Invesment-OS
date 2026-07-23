import hashlib
import os
import re
import time

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from backend.domain.document import DocumentData
from backend.ports.document_source import DocumentSource

load_dotenv()

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik_padded}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

REQUEST_TIMEOUT = 15
RATE_LIMIT_DELAY = 0.12  # SEC allows at most 10 requests/second

# We skip oversized filings rather than truncating them: a verdict drawn from half a
# document is worse than no verdict, because it looks just as confident.
MAX_DOCUMENT_CHARS = 50000


class EdgarError(Exception):
    """Base for every EDGAR failure, so callers can catch this one broadly."""


class EdgarAuthError(EdgarError):
    """403 — the SEC rejected our User-Agent."""


class EdgarRateLimitError(EdgarError):
    """429 — we exceeded the SEC's rate limit."""


class EdgarNotFoundError(EdgarError):
    """404, or a ticker/filing that simply isn't there."""


class EdgarNetworkError(EdgarError):
    """Timeout or connection failure."""


class DocumentTooLargeError(EdgarError):
    """Filing exceeds MAX_DOCUMENT_CHARS — skipped, never truncated."""


def _user_agent() -> str:
    user_agent = os.getenv("SEC_USER_AGENT")
    if not user_agent:
        raise EdgarAuthError(
            "SEC_USER_AGENT is not set. The SEC requires a User-Agent naming the app and a "
            "contact email, e.g. 'Investment OS (you@example.com)'. Requests without one get 403."
        )
    return user_agent


class EdgarSource(DocumentSource):
    def __init__(self) -> None:
        self._ticker_map: dict[str, str] | None = None

    def _get(self, url: str) -> httpx.Response:
        time.sleep(RATE_LIMIT_DELAY)  # stay under the 10 req/sec ceiling

        try:
            response = httpx.get(
                url, headers={"User-Agent": _user_agent()}, timeout=REQUEST_TIMEOUT
            )
        except httpx.TimeoutException as exc:
            raise EdgarNetworkError(f"Timed out after {REQUEST_TIMEOUT}s fetching {url}") from exc
        except httpx.HTTPError as exc:
            raise EdgarNetworkError(f"Network error fetching {url}: {exc}") from exc

        if response.status_code == 403:
            raise EdgarAuthError(
                f"SEC returned 403 for {url}. Check that SEC_USER_AGENT identifies the app "
                "and includes a contact email."
            )
        if response.status_code == 429:
            raise EdgarRateLimitError(
                f"SEC returned 429 (rate limited) for {url}. Back off before retrying — "
                "do not retry immediately."
            )
        if response.status_code == 404:
            raise EdgarNotFoundError(f"SEC returned 404 for {url}")
        if response.status_code != 200:
            raise EdgarError(f"SEC returned HTTP {response.status_code} for {url}")

        return response

    def resolve_cik(self, ticker: str) -> str | None:
        if self._ticker_map is None:
            # Payload is keyed by row index: {"0": {"cik_str": 1045810, "ticker": "NVDA", ...}}
            # cik_str is a number, so it needs zero-padding to the 10-digit form.
            payload = self._get(TICKERS_URL).json()
            self._ticker_map = {
                entry["ticker"].upper(): f"{int(entry['cik_str']):010d}"
                for entry in payload.values()
            }

        return self._ticker_map.get(ticker.upper())

    def list_recent_filings(
        self,
        cik: str,
        form_types: tuple[str, ...] = ("8-K",),
        limit: int = 5,
        ticker: str | None = None,
    ) -> list[dict]:
        payload = self._get(SUBMISSIONS_URL.format(cik_padded=cik)).json()
        recent = payload.get("filings", {}).get("recent", {})

        # Used to build a display title; falls back to the filing's own metadata.
        label = ticker or (payload.get("tickers") or [""])[0]

        forms = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        accession_numbers = recent.get("accessionNumber", [])
        primary_documents = recent.get("primaryDocument", [])

        wanted = {form_type.upper() for form_type in form_types}
        cik_trimmed = str(int(cik))  # archive paths use the CIK without leading zeros

        filings: list[dict] = []
        for index, form in enumerate(forms):  # SEC returns these newest first
            if len(filings) >= limit:
                break
            if form.upper() not in wanted:
                continue

            primary_document = primary_documents[index] if index < len(primary_documents) else ""
            if not primary_document:
                continue  # never guess the document name — skip the filing instead

            accession_number = accession_numbers[index]
            filing_date = filing_dates[index]
            filings.append(
                {
                    "form": form,
                    "filingDate": filing_date,
                    "accessionNumber": accession_number,
                    "primaryDocument": primary_document,
                    "url": ARCHIVE_URL.format(
                        cik=cik_trimmed,
                        accession=accession_number.replace("-", ""),
                        document=primary_document,
                    ),
                    # Ready to hand straight to load() as the title, e.g. "NVDA 8-K 2026-01-15".
                    "title": " ".join(part for part in (label, form, filing_date) if part),
                }
            )

        return filings

    def fetch_filing_text(self, url: str) -> str:
        soup = BeautifulSoup(self._get(url).text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()

        text = soup.get_text(separator=" ")
        return re.sub(r"\s+", " ", text).strip()

    def load(self, ref: str, title: str | None = None) -> DocumentData:
        # For edgar, `ref` is a filing URL — use list_recent_filings() to find one.
        text = self.fetch_filing_text(ref)
        if not text:
            # Empty text would yield confident-looking but meaningless verdicts.
            raise EdgarError(f"No readable text extracted from {ref}")

        if len(text) > MAX_DOCUMENT_CHARS:
            raise DocumentTooLargeError(
                f"Filing at {ref} is {len(text)} characters, over the {MAX_DOCUMENT_CHARS} "
                "character limit. Skipping rather than truncating."
            )

        return DocumentData(
            source_type="edgar",
            title=title or "filing",
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            raw_text=text,
        )
