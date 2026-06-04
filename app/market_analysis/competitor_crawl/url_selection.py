"""SERP URL selection for controlled competitor crawling."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.market_analysis.competitor_crawl.models import CompetitorCrawlTarget

_BLOCKED_PATH_PARTS = (
    "/cart",
    "/checkout",
    "/account",
    "/search",
    "/login",
    "/register",
)

_TRACKING_QUERY_PREFIXES = ("utm_",)
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "msclkid", "mc_cid", "mc_eid"}


def select_competitor_urls_for_product(
    product_keywords: list[dict],
    serp_intel: dict[str, dict],
    merchant_domain: str,
    max_urls: int,
    merchant_domains: list[str] | None = None,
) -> list[CompetitorCrawlTarget]:
    """Select top external competitor URLs from DataForSEO SERP intelligence."""
    if max_urls <= 0:
        return []
    merchants = {
        domain
        for domain in [_normalize_domain(merchant_domain)]
        + [_normalize_domain(value) for value in (merchant_domains or [])]
        if domain
    }
    selected: list[CompetitorCrawlTarget] = []
    seen_urls: set[str] = set()
    keywords = sorted(
        [kw for kw in product_keywords if isinstance(kw, dict) and kw.get("query")],
        key=lambda kw: int(kw.get("target_rank", 999) or 999),
    )
    for keyword in keywords[:2]:
        query = str(keyword.get("query", "")).strip()
        if not query:
            continue
        intel = serp_intel.get(query.lower()) or serp_intel.get(query)
        if not isinstance(intel, dict):
            continue
        competitors = [
            item for item in intel.get("top_competitors", []) or [] if isinstance(item, dict)
        ]
        competitors.sort(key=lambda item: int(item.get("rank", 999) or 999))
        for item in competitors:
            url = str(item.get("url") or "").strip()
            canonical_url = canonicalize_competitor_url(url)
            if not canonical_url or canonical_url in seen_urls:
                continue
            domain = _normalize_domain(str(item.get("domain") or urlsplit(canonical_url).netloc))
            if not domain or any(_same_or_subdomain(domain, merchant) for merchant in merchants):
                continue
            if _is_blocked_path(canonical_url):
                continue
            rank = int(item.get("rank", 999) or 999)
            selected.append(
                CompetitorCrawlTarget(
                    keyword=query,
                    rank=rank,
                    domain=domain,
                    url=canonical_url,
                    title=str(item.get("title") or "").strip(),
                )
            )
            seen_urls.add(canonical_url)
            if len(selected) >= max_urls:
                return sorted(selected, key=lambda target: (target.rank > 5, target.rank))
    return sorted(selected, key=lambda target: (target.rank > 5, target.rank))


def canonicalize_competitor_url(url: str) -> str:
    """Return a stable HTTP(S) URL without fragments or tracking parameters."""
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return ""
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        return ""
    host = parsed.netloc.lower()
    if not host:
        return ""
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_QUERY_KEYS
        and not key.lower().startswith(_TRACKING_QUERY_PREFIXES)
    ]
    path = parsed.path or "/"
    return urlunsplit((scheme, host, path, urlencode(query_items), ""))


def _normalize_domain(value: str) -> str:
    raw = value.strip().lower()
    if not raw:
        return ""
    if "://" in raw:
        raw = urlsplit(raw).netloc.lower()
    raw = raw.split("/")[0].split(":")[0].removeprefix("www.")
    return raw


def _same_or_subdomain(domain: str, merchant_domain: str) -> bool:
    if not domain or not merchant_domain:
        return False
    return domain == merchant_domain or domain.endswith(f".{merchant_domain}")


def _is_blocked_path(url: str) -> bool:
    path = urlsplit(url).path.lower().rstrip("/")
    return any(path == part or path.startswith(f"{part}/") for part in _BLOCKED_PATH_PARTS)
