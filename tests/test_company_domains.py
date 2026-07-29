from backend.domain.company_domains import (
    ICONS_KNOWN_BAD,
    TICKER_DOMAINS,
    domain_for_ticker,
    logo_url_for_ticker,
)
from backend.domain.market_leaders import MARKET_LEADERS


# --- the map -----------------------------------------------------------------------


def test_every_market_leader_has_a_domain():
    # The market page is the most visible use of this map; an unmapped leader is a
    # bare initials box on the front of the app.
    missing = [t for t in MARKET_LEADERS if t not in TICKER_DOMAINS]
    assert missing == []


def test_lookup_normalises_case_and_whitespace():
    assert domain_for_ticker("  nvda ") == "nvidia.com"


def test_an_unmapped_ticker_returns_none_rather_than_a_guess():
    # A guessed "{ticker}.com" would put a stranger's brand beside someone's thesis.
    assert domain_for_ticker("ZZZZ") is None
    assert logo_url_for_ticker("ZZZZ") is None


def test_both_berkshire_share_class_notations_are_mapped():
    # No agreed convention: the dot form is how these are usually written, Yahoo
    # uses a hyphen. Mapping one silently drops the other.
    for ticker in ("BRK.B", "BRK-B", "BRK.A", "BRK-A"):
        assert domain_for_ticker(ticker) == "berkshirehathaway.com"


# --- the known-bad icon list --------------------------------------------------------


def test_known_bad_icons_yield_no_logo_url():
    # ⚠️ THE POINT OF THIS LIST. The icon service returns a 200 with a WRONG image
    # for these — a rival's wordmark for TSM, a generic placeholder for Berkshire —
    # so the browser's onError never fires and the frontend cannot detect it. The
    # only place it can be caught is here.
    for ticker in ICONS_KNOWN_BAD:
        assert logo_url_for_ticker(ticker) is None, ticker


def test_known_bad_tickers_keep_their_domain():
    # The domains are CORRECT and stay queryable; only logo derivation is suppressed.
    # Deleting the mapping instead would throw away a true fact to fix a false image.
    assert domain_for_ticker("TSM") == "tsmc.com"
    assert domain_for_ticker("BRK-B") == "berkshirehathaway.com"


def test_healthy_leaders_still_get_a_logo():
    # The suppression must be surgical — everything verified good keeps its mark.
    for ticker in ("AAPL", "NVDA", "GOOGL", "MSFT", "AMZN", "AVGO", "META", "TSLA",
                   "LLY", "JPM"):
        url = logo_url_for_ticker(ticker)
        assert url is not None and url.startswith("https://"), ticker
