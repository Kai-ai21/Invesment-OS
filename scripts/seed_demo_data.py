#!/usr/bin/env python
"""Populate a fresh database by driving the app's own HTTP API.

⚠️ IT TALKS HTTP AND NOTHING ELSE. There is not a single `from backend...` import
below, and that is the whole design. Claims are written by the extraction pipeline
and evidence by the verification pipeline — the same code paths a real user goes
through — so what lands in the database is what the app actually produces, citation
check and all. A script that INSERTed claims directly would be seeding data the app
could never have generated: quotes that were never validated against a source, claim
statuses that no status computation produced, and a demo that silently stops matching
the product the first time either pipeline changes.

The cost of that choice is that seeding is slow and metered, because every thesis and
every document is real AI work. See PACING.

USAGE
    python -m scripts.seed_demo_data BASE_URL EMAIL SEED_FILE
    python -m scripts.seed_demo_data http://127.0.0.1:8000 you@example.com seed.json
    python -m scripts.seed_demo_data ... --dry-run     # validate and plan, call nothing

The password is PROMPTED FOR, never an argument. A command-line password lands in your
shell history file and is visible in `ps` to every other user on the machine for as
long as the process runs — and this process runs for a long time.

PACING
The free Groq tier meters TOKENS PER MINUTE, and one document costs more than a
minute's worth, so the script paces itself instead of hoping. Two things are worth
knowing about where the cost actually is:

  - A THESIS is one AI call. The extraction prompt plus your reasoning plus 2-4 claims
    of output — a couple of thousand tokens.
  - A DOCUMENT is ONE CALL PER CLAIM. verification_service loops over the thesis's
    claims and verifies each against its own retrieved passages, so a 3-claim thesis
    means 3 calls for one document. That is why a document costs roughly 9,000 tokens
    against a thesis's 2,000, and why the sleep between documents is over a minute.

RE-RUNNING IS SAFE AND CHEAP
A thesis whose ticker already exists is reused rather than re-extracted, and a document
the app has already verified against that thesis is recognised by content hash and
returns its existing evidence without spending a token. A resumed run skips the sleep
for those, so picking up where a failed run stopped takes seconds, not an hour.

⚠️ ONE FAILURE MODE THE APP CANNOT CURRENTLY RECOVER FROM, and it is why this script
warns rather than pretending. Evidence events are committed one at a time
(evidence_repository.create_evidence_event), so a document that dies part-way — the
rate limit landing on claim 3 of 3 — leaves the first two claims' evidence committed
and the document recorded. Every later attempt then sees "this thesis already has
evidence from this document" and short-circuits, so claim 3 is never verified and
nothing says so. The script detects the signature of this (a failed attempt followed by
a suspiciously instant success) and tells you. There is no re-verify endpoint and no
DELETE /theses, so the fix is a fresh database rather than another run.
"""

from __future__ import annotations

import argparse
import getpass
import json
import math
import re
import time
from pathlib import Path
from typing import NamedTuple

import httpx

# --- the rate limit this whole script exists to respect ---------------------------

# Groq's free tier, as documented at the time of writing. Overridable because it is
# the one number here that is somebody else's policy rather than a fact about this app.
DEFAULT_TOKENS_PER_MINUTE = 8_000

# ⚠️ THESE ARE ESTIMATES, AND DELIBERATELY GENEROUS ONES. Nothing reports actual token
# usage back through the API, so the pacer works from a forecast; forecasting low means
# hitting the limit, which costs a 45-second backoff and possibly a half-verified
# document. Forecasting high costs nothing but wall-clock time on a script you run once.
#
# The document figure assumes roughly three claims at roughly 3,000 tokens each: the
# verification prompt, eight retrieved passages (~6,400 characters — see
# verification_service._RETRIEVAL_K), and a short structured verdict.
DEFAULT_TOKENS_PER_DOCUMENT = 9_000
DEFAULT_TOKENS_PER_THESIS = 2_000

# --- retry behaviour ---------------------------------------------------------------

RETRY_ATTEMPTS = 5

# ⚠️ THE FIRST BACKOFF IS LONG ON PURPOSE. A tokens-per-minute ceiling refills over a
# MINUTE; retrying a rate limit after two seconds just spends another attempt on the
# same closed door. Starting near the width of the window is the only wait that can
# actually change the answer.
INITIAL_BACKOFF_SECONDS = 45.0
MAX_BACKOFF_SECONDS = 300.0

# ⚠️ A RATE LIMIT DOES NOT REACH THIS SCRIPT AS A 429, and assuming it did was the
# first thing to get wrong here. Groq's own SDK retries 429s inside the backend, and
# what finally escapes is reshaped on the way out:
#
#   POST /theses            -> 422. extraction_service catches EVERY exception, retries
#                              three times, then raises ExtractionError, which the route
#                              turns into a 422 whose detail carries the original error.
#   POST /theses/{id}/docs  -> 500. verification_service does not wrap the provider call
#                              at all, so the exception becomes an unhandled 500.
#
# 429 is still listed because a proxy, load balancer or CDN in front of a deployed API
# can produce one before the request ever reaches the app.
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}

# Used ONLY to decide whether a 422 was a rate limit wearing a validation code. A 422
# that says "Expected 2-4 claims, got 1" is a real answer about your reasoning text and
# retrying it just burns tokens to be told the same thing again.
_TRANSIENT_DETAIL = re.compile(
    r"rate.?limit|429|too many requests|timed? ?out|timeout|connection|overloaded|"
    r"temporarily|service unavailable|try again",
    re.IGNORECASE,
)

# Below this, a documents POST cannot have run the model — verification is several
# seconds of network round-trips per claim at the very best. So a sub-second response
# means the content hash matched and the app returned existing evidence, which costs
# nothing and must not be followed by a minute of sleeping.
NOOP_SECONDS = 3.0

# Read timeout sized for the worst legitimate case: every claim verified in sequence,
# each with the Groq SDK's own internal retries underneath it. Connect stays short —
# a wrong base URL should fail immediately, not in ten minutes.
HTTP_TIMEOUT = httpx.Timeout(connect=10.0, read=600.0, write=60.0, pool=10.0)


class SeedError(Exception):
    """Anything that should stop the run with a sentence rather than a traceback."""


class Reply(NamedTuple):
    """One completed call.

    ⚠️ `seconds` TIMES THE SUCCESSFUL ATTEMPT ONLY, not the whole retry sequence, and
    that distinction is load-bearing. The caller reads this duration to tell a real
    verification from a deduplicated no-op, and a retry that slept 45 seconds before
    succeeding instantly would otherwise look like the most expensive call of the run
    — which is exactly backwards, and would hide the half-verified-document warning.
    """

    response: httpx.Response
    seconds: float
    retried: bool


def say(message: str = "") -> None:
    """Progress goes to stdout, flushed.

    Unbuffered because this script spends most of its life asleep, and progress you
    cannot see until the process exits is not progress. `| tee seed.log` works too.
    """
    print(message, flush=True)


# --- the seed file -----------------------------------------------------------------


def load_seed_file(path: Path) -> list[dict]:
    """Read and fully validate the seed file. Raises SeedError with what to fix.

    ⚠️ EVERYTHING IS CHECKED BEFORE A SINGLE REQUEST IS SENT, including reading every
    external document off disk. The alternative is discovering a typo in the fourth
    thesis forty minutes and several thousand tokens into a run, with three theses
    already half-seeded into a database that has no delete endpoint.
    """
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        raise SeedError(f"no seed file at {path}")
    except json.JSONDecodeError as exc:
        raise SeedError(f"{path} is not valid JSON: {exc}")

    if not isinstance(raw, dict) or "theses" not in raw:
        raise SeedError(
            f'{path} must be a JSON object with a "theses" key. See the module '
            "docstring for the shape."
        )

    entries = raw["theses"]
    if not isinstance(entries, list) or not entries:
        raise SeedError('"theses" must be a non-empty list.')

    seen_tickers: set[str] = set()
    theses: list[dict] = []

    for index, entry in enumerate(entries, start=1):
        where = f'theses[{index - 1}]'
        if not isinstance(entry, dict):
            raise SeedError(f"{where} is not an object.")

        ticker = str(entry.get("ticker") or "").strip().upper()
        if not ticker:
            raise SeedError(f"{where} has no ticker.")
        # Upper-cased above, so this catches "nvda" and "NVDA" as the same duplicate.
        # Two entries for one ticker would silently seed only the first: the second
        # would find the ticker already present and skip itself as though resumed.
        if ticker in seen_tickers:
            raise SeedError(f"{where}: ticker {ticker} appears more than once.")
        seen_tickers.add(ticker)

        reasoning = str(entry.get("reasoning") or "").strip()
        if not reasoning:
            raise SeedError(f"{where} ({ticker}) has no reasoning.")

        raw_documents = entry.get("documents", [])
        if not isinstance(raw_documents, list):
            raise SeedError(f"{where} ({ticker}): documents must be a list.")

        documents = [
            _load_document(document, f"{where}.documents[{position}]", ticker, path)
            for position, document in enumerate(raw_documents)
        ]

        theses.append({"ticker": ticker, "reasoning": reasoning, "documents": documents})

    return theses


def _load_document(document: object, where: str, ticker: str, seed_path: Path) -> dict:
    """One document, with its text resolved to a string whichever way it was given."""
    if not isinstance(document, dict):
        raise SeedError(f"{where} is not an object.")

    title = document.get("title")
    if title is not None:
        title = str(title).strip() or None

    has_text = "text" in document
    has_path = "path" in document
    if has_text == has_path:
        raise SeedError(
            f'{where} ({ticker}) must have exactly one of "text" or "path", not '
            f"{'both' if has_text else 'neither'}."
        )

    if has_text:
        text = str(document["text"] or "")
        source = "inline"
    else:
        # ⚠️ RESOLVED AGAINST THE SEED FILE'S OWN DIRECTORY, not the working directory.
        # The paths live in that file, so they should mean the same thing however the
        # script is invoked — otherwise the file only works from one cwd.
        document_path = (seed_path.parent / str(document["path"])).resolve()
        try:
            text = document_path.read_text()
        except OSError as exc:
            raise SeedError(f"{where} ({ticker}): cannot read {document_path}: {exc}")
        source = str(document_path)

    if not text.strip():
        raise SeedError(f"{where} ({ticker}) has empty text.")

    return {"title": title, "text": text, "source": source}


# --- pacing ------------------------------------------------------------------------


class Pacer:
    """Holds the run under a tokens-per-minute ceiling.

    Charge it what an operation cost, and it will not let the next one start until
    that many tokens' worth of time has passed. Modelled per-token rather than as a
    fixed sleep between documents so that a cheap thesis extraction does not buy the
    same sixty-eight second penalty an expensive document does.

    ⚠️ IT IS CHARGED ONLY FOR WORK THAT ACTUALLY HAPPENED. A document the app already
    had, or a thesis that already existed, spends nothing and must not be paced — that
    is what makes resuming a failed run cheap instead of another full-length wait.
    """

    def __init__(self, tokens_per_minute: int) -> None:
        self._seconds_per_token = 60.0 / tokens_per_minute
        self._tokens_per_minute = tokens_per_minute
        self._next_allowed = 0.0

    def seconds_for(self, tokens: int) -> float:
        return tokens * self._seconds_per_token

    def charge(self, tokens: int) -> None:
        self._next_allowed = time.monotonic() + self.seconds_for(tokens)

    def wait(self, what: str) -> None:
        remaining = self._next_allowed - time.monotonic()
        if remaining <= 0:
            return
        say(
            f"       pacing {remaining:.0f}s before {what} "
            f"({self._tokens_per_minute:,} tokens/min)"
        )
        time.sleep(remaining)


# --- the API client ----------------------------------------------------------------


class Api:
    """The app's HTTP API, with the retries this script needs and nothing else."""

    def __init__(self, base_url: str, client: httpx.Client) -> None:
        self._base = base_url.rstrip("/")
        self._client = client
        self._token: str | None = None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    def health(self) -> None:
        """Fail on a wrong URL now, before asking for a password."""
        try:
            response = self._client.get(f"{self._base}/health", timeout=15.0)
        except httpx.RequestError as exc:
            raise SeedError(
                f"cannot reach {self._base}: {type(exc).__name__}: {exc}\n"
                "  Check the base URL, and that the API is running."
            )
        if response.status_code != 200:
            raise SeedError(
                f"{self._base}/health answered {response.status_code}, not 200. "
                "That is not this app, or it is not healthy."
            )

    def log_in(self, email: str, password: str) -> None:
        response = self._client.post(
            f"{self._base}/auth/login", json={"email": email, "password": password}
        )
        if response.status_code == 401:
            # The API answers every login failure identically on purpose (see
            # api/auth.py), so this cannot say which half was wrong — and neither can
            # this message, honestly.
            raise SeedError(
                f"the API refused those credentials for {email}.\n"
                "  It answers the same way for a wrong password and an unknown "
                "address, so check both."
            )
        if response.status_code != 200:
            raise SeedError(f"login failed: {_describe(response)}")

        self._token = response.json()["access_token"]
        # ⚠️ The token is never printed. It is a bearer credential for this account for
        # a full day, and this script's output is the sort of thing that gets pasted
        # into a terminal transcript or a `tee`d log.

    def existing_tickers(self) -> dict[str, str]:
        """ticker -> thesis id, for everything this account already has."""
        reply = self._request("GET", "/theses", label="listing existing theses")
        return {thesis["ticker"].upper(): thesis["id"] for thesis in reply.response.json()}

    def create_thesis(self, ticker: str, reasoning: str) -> dict:
        return self._request(
            "POST",
            "/theses",
            json={"ticker": ticker, "reasoning": reasoning},
            label=f"extracting claims for {ticker}",
        ).response.json()

    def submit_document(self, thesis_id: str, text: str, title: str | None) -> Reply:
        return self._request(
            "POST",
            f"/theses/{thesis_id}/documents",
            json={"raw_text": text, "title": title},
            label=f"verifying {title or 'document'}",
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        label: str,
    ) -> Reply:
        """One call, retried while the failure looks like it might pass.

        ⚠️ RETRYING A WRITE IS SAFE HERE ONLY BECAUSE OF WHAT THESE TWO ENDPOINTS DO.
        POST /theses/{id}/documents deduplicates on the document's content hash, so a
        second attempt either resumes or returns what already exists rather than
        duplicating it. POST /theses does NOT deduplicate — it would happily create a
        second NVDA thesis — which is why it is only ever called for a ticker the
        caller has just confirmed is absent, and why a failure there is reported
        rather than retried into a mess. Do not add a retrying write to this method
        without checking the same question.
        """
        delay = INITIAL_BACKOFF_SECONDS
        failed_once = False

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            attempt_started = time.monotonic()
            try:
                response = self._client.request(
                    method, f"{self._base}{path}", json=json, headers=self._headers()
                )
            except httpx.RequestError as exc:
                reason = f"{type(exc).__name__}: {exc}"
                retry_after = None
            else:
                if response.status_code < 400:
                    return Reply(response, time.monotonic() - attempt_started, failed_once)
                if not _is_transient(response):
                    raise SeedError(f"{label} failed: {_describe(response)}")
                reason = _describe(response)
                retry_after = _retry_after(response)

            failed_once = True
            if attempt == RETRY_ATTEMPTS:
                raise SeedError(
                    f"{label} failed after {RETRY_ATTEMPTS} attempts. Last: {reason}"
                )

            wait = retry_after if retry_after is not None else delay
            say(f"       attempt {attempt} failed ({reason})")
            say(f"       retrying in {wait:.0f}s")
            time.sleep(wait)
            delay = min(delay * 2, MAX_BACKOFF_SECONDS)

        raise AssertionError("unreachable")  # pragma: no cover


def _is_transient(response: httpx.Response) -> bool:
    if response.status_code in _TRANSIENT_STATUS:
        return True
    if response.status_code != 422:
        return False

    # A 422 is either FastAPI's own schema validation (detail is a LIST of field
    # errors — never transient, the request itself is malformed) or the route's
    # ExtractionError (detail is a STRING carrying the underlying cause). Only the
    # second can be a rate limit in disguise.
    detail = _detail(response)
    return isinstance(detail, str) and bool(_TRANSIENT_DETAIL.search(detail))


def _detail(response: httpx.Response):
    try:
        return response.json().get("detail")
    except (ValueError, AttributeError):
        return None


def _describe(response: httpx.Response) -> str:
    detail = _detail(response)
    if detail is None:
        detail = response.text[:200] or "(no body)"
    return f"HTTP {response.status_code}: {detail}"


def _retry_after(response: httpx.Response) -> float | None:
    """Honour Retry-After when something upstream sets it; it beats our guess."""
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None  # The HTTP-date form. Rare here, and our own backoff is fine.


# --- the run -----------------------------------------------------------------------


def seed(api: Api, theses: list[dict], pacer: Pacer, tokens: dict[str, int]) -> int:
    """Walk the seed file. Returns the number of theses that ended up incomplete."""
    existing = api.existing_tickers()
    if existing:
        say(f"This account already has {len(existing)} thesis/theses: "
            f"{', '.join(sorted(existing))}")
        say("Those will be reused, not recreated.\n")

    warnings = 0

    for index, entry in enumerate(theses, start=1):
        ticker = entry["ticker"]
        say(f"[{index}/{len(theses)}] {ticker}")

        thesis_id = existing.get(ticker)
        if thesis_id is not None:
            say(f"       thesis: already exists, reusing ({thesis_id})")
        else:
            pacer.wait("claim extraction")
            started = time.monotonic()
            thesis = api.create_thesis(ticker, entry["reasoning"])
            pacer.charge(tokens["thesis"])
            thesis_id = thesis["id"]
            claims = thesis.get("claims", [])
            say(f"       thesis: created in {time.monotonic() - started:.1f}s "
                f"— {len(claims)} claims")
            for claim in claims:
                flag = "" if claim.get("verifiability") != "unverifiable" else "  [filings won't answer this]"
                say(f"         - {claim['statement'][:88]}{flag}")

        documents = entry["documents"]
        if not documents:
            say("       no documents for this thesis\n")
            continue

        for position, document in enumerate(documents, start=1):
            name = document["title"] or f"document {position}"
            pacer.wait(f"document {position}/{len(documents)}")
            say(f"       doc {position}/{len(documents)}: {name}")

            reply = api.submit_document(thesis_id, document["text"], document["title"])
            events = reply.response.json()

            if reply.seconds < NOOP_SECONDS:
                # Nothing was spent, so nothing is charged and the next document
                # starts immediately.
                say(f"       -> already verified, skipped ({reply.seconds:.1f}s, "
                    f"{len(events)} existing events)")
                if reply.retried:
                    # See the module docstring: a failure followed by an instant
                    # success is what a half-verified document looks like from here.
                    warnings += 1
                    say("       ⚠️  WARNING: this document failed an attempt and then "
                        "returned instantly.")
                    say("           That is the signature of a document whose "
                        "verification died part-way:")
                    say("           the app now considers it done and will not "
                        "re-verify the remaining claims.")
                    say("           Seed a fresh database if this thesis needs to be "
                        "complete.")
            else:
                pacer.charge(tokens["document"])
                say(f"       -> {len(events)} evidence events in {reply.seconds:.1f}s")

        say("")

    return warnings


def plan(theses: list[dict], pacer: Pacer, tokens: dict[str, int]) -> None:
    """What the run will do, and roughly how long you are committing to."""
    documents = sum(len(entry["documents"]) for entry in theses)
    seconds = (
        len(theses) * pacer.seconds_for(tokens["thesis"])
        + documents * pacer.seconds_for(tokens["document"])
    )

    say(f"{len(theses)} thesis/theses, {documents} document(s).")
    for entry in theses:
        say(f"  {entry['ticker']:<6} {len(entry['documents'])} document(s)")
        for document in entry["documents"]:
            title = document["title"] or "(untitled)"
            say(f"           - {title}  [{document['source']}, "
                f"{len(document['text']):,} chars]")
    say("")
    say(f"Paced at {tokens['thesis']:,} tokens per thesis and "
        f"{tokens['document']:,} per document,")
    say(f"a complete run takes at least {math.ceil(seconds / 60)} minutes of mostly "
        "sleeping.")
    say("Anything already seeded is skipped and costs nothing.")
    say("")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="seed_demo_data",
        description="Populate a database through the app's own API, so claims and "
        "evidence come from the real extraction and verification pipelines.",
    )
    parser.add_argument("base_url", help="e.g. http://127.0.0.1:8000")
    parser.add_argument("email", help="the account to seed into; it must already exist")
    parser.add_argument("seed_file", type=Path, help="the JSON described in this module's docstring")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the seed file and print the plan. Sends no requests and asks "
        "for no password.",
    )
    parser.add_argument(
        "--tokens-per-minute",
        type=int,
        default=DEFAULT_TOKENS_PER_MINUTE,
        help=f"the provider's rate limit. Default {DEFAULT_TOKENS_PER_MINUTE:,} "
        "(Groq free tier). Raise it on a paid tier to go faster.",
    )
    parser.add_argument(
        "--tokens-per-document",
        type=int,
        default=DEFAULT_TOKENS_PER_DOCUMENT,
        help=f"estimated cost of verifying one document against one thesis. Default "
        f"{DEFAULT_TOKENS_PER_DOCUMENT:,}. Raise it if your theses carry four claims "
        "or your documents are long.",
    )
    args = parser.parse_args(argv)

    tokens = {"thesis": DEFAULT_TOKENS_PER_THESIS, "document": args.tokens_per_document}

    try:
        theses = load_seed_file(args.seed_file)
    except SeedError as exc:
        say(f"Refusing to run: {exc}")
        return 1

    pacer = Pacer(args.tokens_per_minute)
    plan(theses, pacer, tokens)

    if args.dry_run:
        say("Dry run: nothing was sent.")
        return 0

    with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        api = Api(args.base_url, client)
        try:
            api.health()
            # Asked for only after the seed file parsed and the API answered, so a
            # typo in either does not cost you a password prompt first.
            password = getpass.getpass(f"Password for {args.email}: ")
            api.log_in(args.email, password)
            say(f"Logged in as {args.email}.\n")

            started = time.monotonic()
            warnings = seed(api, theses, pacer, tokens)
        except SeedError as exc:
            say(f"\nStopped: {exc}")
            say("Re-running is safe: finished work is skipped and costs nothing.")
            return 1
        except KeyboardInterrupt:
            say("\nInterrupted. Re-running is safe — finished work is skipped.")
            return 130

    say(f"Done in {(time.monotonic() - started) / 60:.1f} minutes.")
    if warnings:
        say(f"⚠️  {warnings} document(s) may be only partly verified — see the "
            "warnings above.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
