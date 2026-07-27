"""Ticker -> primary web domain, for deriving company logos.

WHY A HAND-WRITTEN MAP. There is no free, reliable ticker-to-domain service, and the
mapping cannot be inferred: NVDA is nvidia.com but BRK.B is berkshirehathaway.com, GOOGL
is google.com, and TXN is ti.com. Guessing "{ticker}.com" would produce confidently
WRONG logos — showing a stranger's brand next to someone's investment thesis is worse
than showing no logo at all — so an unmapped ticker returns None and the UI falls back
to its initials.

This is DELIBERATELY a small curated list covering the largest US companies, which is
what a personal watchlist mostly holds. Full coverage would need a financial data API
(FMP, Polygon, IEX and similar all expose company profiles including a website field),
and that is the upgrade path if this list starts feeling short.

WHY FAVICONS, NOT CLEARBIT. The obvious choice was Clearbit's free logo endpoint. It is
GONE: logo.clearbit.com no longer resolves at all (NXDOMAIN, verified — while
clearbit.com itself still resolves), following the HubSpot acquisition. The company's
own favicon by domain is the working substitute, and it is the same service already used
for news publisher icons, so there is one fewer third party in the stack.
"""

# Largest US listings by market capitalisation, plus a few this project is likely to
# touch. Keys are upper-case; look-ups normalise.
TICKER_DOMAINS: dict[str, str] = {
    "AAPL": "apple.com",
    "MSFT": "microsoft.com",
    "NVDA": "nvidia.com",
    "GOOGL": "google.com",
    "GOOG": "google.com",
    "AMZN": "amazon.com",
    "META": "meta.com",
    "TSLA": "tesla.com",
    "AVGO": "broadcom.com",
    "BRK.B": "berkshirehathaway.com",
    "BRK.A": "berkshirehathaway.com",
    "LLY": "lilly.com",
    "JPM": "jpmorganchase.com",
    "V": "visa.com",
    "MA": "mastercard.com",
    "XOM": "exxonmobil.com",
    "UNH": "unitedhealthgroup.com",
    "COST": "costco.com",
    "HD": "homedepot.com",
    "PG": "pg.com",
    "JNJ": "jnj.com",
    "WMT": "walmart.com",
    "NFLX": "netflix.com",
    "ABBV": "abbvie.com",
    "CRM": "salesforce.com",
    "BAC": "bankofamerica.com",
    "ORCL": "oracle.com",
    "CVX": "chevron.com",
    "KO": "coca-colacompany.com",
    "AMD": "amd.com",
    "PEP": "pepsico.com",
    "TMO": "thermofisher.com",
    "ADBE": "adobe.com",
    "MRK": "merck.com",
    "CSCO": "cisco.com",
    "ACN": "accenture.com",
    "MCD": "mcdonalds.com",
    "ABT": "abbott.com",
    "INTC": "intel.com",
    "IBM": "ibm.com",
    "QCOM": "qualcomm.com",
    "TXN": "ti.com",
    "DIS": "disney.com",
    "INTU": "intuit.com",
    "AMAT": "appliedmaterials.com",
    "GE": "ge.com",
    "CAT": "caterpillar.com",
    "VZ": "verizon.com",
    "PFE": "pfizer.com",
    "NOW": "servicenow.com",
    "UBER": "uber.com",
    "BA": "boeing.com",
    "SBUX": "starbucks.com",
    "PYPL": "paypal.com",
    "SHOP": "shopify.com",
    "PLTR": "palantir.com",
    "MU": "micron.com",
    "ARM": "arm.com",
    "SMCI": "supermicro.com",
    "DELL": "dell.com",
    "TSM": "tsmc.com",
}

# Same service as the news publisher favicons. Derived from the domain, never fetched
# server-side: the browser loads it lazily and caches it per domain.
_FAVICON_URL = "https://icons.duckduckgo.com/ip3/{domain}.ico"


def domain_for_ticker(ticker: str | None) -> str | None:
    """The company's primary domain, or None when the ticker is not in the map.

    None is a real answer — never a guessed domain.
    """
    if not ticker:
        return None
    return TICKER_DOMAINS.get(ticker.strip().upper())


def logo_url_for_ticker(ticker: str | None) -> str | None:
    """A logo URL for the ticker, or None when there is no known domain.

    None means the UI should show its initials fallback. Note the icon service answers
    404 for a domain it has no icon for, but with a generic placeholder image in the
    BODY, which browsers render rather than treating as an error — so a mapped company
    whose icon is missing shows a neutral placeholder rather than the initials.
    """
    domain = domain_for_ticker(ticker)
    return _FAVICON_URL.format(domain=domain) if domain else None
