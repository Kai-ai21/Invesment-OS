import hashlib
import os
import re
import time
from collections import Counter

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

# A resource safety valve, NOT a context-window limit. Retrieval now chunks a filing
# and shows the model only the passages relevant to each claim, so length no longer
# constrains what we can verify — a full 10-K is fine. What this guards against is the
# pathological input (a mislabelled binary, a runaway download) that would blow up
# memory and embedding time. Oversized filings are still skipped rather than
# truncated: a verdict drawn from half a document is worse than no verdict, because
# it looks just as confident.
MAX_DOCUMENT_CHARS = 1_000_000


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
    """Filing exceeds the MAX_DOCUMENT_CHARS safety valve — skipped, never truncated."""


def _user_agent() -> str:
    user_agent = os.getenv("SEC_USER_AGENT")
    if not user_agent:
        raise EdgarAuthError(
            "SEC_USER_AGENT is not set. The SEC requires a User-Agent naming the app and a "
            "contact email, e.g. 'Investment OS (you@example.com)'. Requests without one get 403."
        )
    return user_agent


# --- page furniture --------------------------------------------------------------
# Filings repeat navigation and running headers on every page ("Table of Contents",
# "<Company> and Subsidiaries", "Notes to the Consolidated Financial Statements
# (Continued)"). Flattened into one blob these dominate retrieval: they read as
# generic financial text, so they rank against any financial query and crowd out the
# real MD&A prose.
#
# We delete whole structural SEGMENTS and never touch the characters of surviving
# prose — no reflowing, no de-hyphenating — because evidence quotes must remain
# verbatim substrings of what we return.
#
# Detection uses the "Table of Contents" page-break marker plus repetition, never a
# company name, so it works for any filer.
_FURNITURE_MIN_REPEATS = 5
_FURNITURE_MAX_CHARS = 200

_TABLE_OF_CONTENTS = re.compile(r"^table of contents$", re.IGNORECASE)
_BARE_INTEGER = re.compile(r"^\d{1,4}$")
_HAS_LETTERS = re.compile(r"[A-Za-z]")


def _recurs_across_document(line: str, counts: Counter) -> bool:
    """Short, wordy, and seen many times — the profile of a running header."""
    return (
        counts[line] >= _FURNITURE_MIN_REPEATS
        and len(line) <= _FURNITURE_MAX_CHARS
        and _HAS_LETTERS.search(line) is not None
    )


def _strip_page_furniture(lines: list[str]) -> list[str]:
    """Drop page-break furniture. Surviving lines are returned unmodified.

    Removal is ANCHORED to the "Table of Contents" navigation marker that EDGAR
    filings emit at every page break, and only extends to the page number just
    before it and the recurring header lines immediately after it.

    Repetition alone is deliberately NOT enough to delete a line. Inline fragments
    like "billion and $" also recur dozens of times, because the HTML splits
    sentences across elements — deleting those silently corrupted a figure
    ("$2.7 billion and $1.1 billion" became "$ 2.7 1.1 billion") during development.
    Requiring the structural anchor keeps the filter off prose and off table cells.
    """
    counts = Counter(lines)
    drop: set[int] = set()

    for index, line in enumerate(lines):
        if not _TABLE_OF_CONTENTS.match(line):
            continue
        drop.add(index)

        # The bare page number printed just before the marker.
        if index and _BARE_INTEGER.match(lines[index - 1]):
            drop.add(index - 1)

        # The running header trailing the marker — e.g. "<Company> and Subsidiaries",
        # "Notes to the Consolidated Financial Statements", "(Continued)". Walk only
        # while the lines keep looking like recurring headers, so the first line of
        # real page content stops the scan.
        following = index + 1
        while following < len(lines) and _recurs_across_document(
            lines[following], counts
        ):
            drop.add(following)
            following += 1

    return [line for index, line in enumerate(lines) if index not in drop]


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

        # Split on element boundaries so page furniture can be dropped whole. Joining
        # the survivors with " " and collapsing whitespace reproduces exactly what
        # separator=" " used to yield for the text we keep — surviving prose is
        # byte-identical, which is what the verbatim citation check depends on.
        lines = [line.strip() for line in soup.get_text(separator="\n").split("\n")]
        kept = _strip_page_furniture([line for line in lines if line])
        return re.sub(r"\s+", " ", " ".join(kept)).strip()

    def load(self, ref: str, title: str | None = None) -> DocumentData:
        # For edgar, `ref` is a filing URL — use list_recent_filings() to find one.
        text = self.fetch_filing_text(ref)
        if not text:
            # Empty text would yield confident-looking but meaningless verdicts.
            raise EdgarError(f"No readable text extracted from {ref}")

        if len(text) > MAX_DOCUMENT_CHARS:
            raise DocumentTooLargeError(
                f"Filing at {ref} is {len(text):,} characters, over the "
                f"{MAX_DOCUMENT_CHARS:,} character safety limit. This is far larger than "
                "any normal filing, so it is skipped rather than truncated."
            )

        return DocumentData(
            source_type="edgar",
            title=title or "filing",
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            raw_text=text,
        )
