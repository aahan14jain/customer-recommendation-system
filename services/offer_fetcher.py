"""Mock offer data keyed by vendor. Not wired into the app yet."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

OfferDict = dict[str, str | int]

# Relative band around predicted_spend for “realistic” matches (±40%).
_PRICE_BAND_LOW = 0.6
_PRICE_BAND_HIGH = 1.4

_OFFERS_JSON = Path(__file__).resolve().parent / "mock_offers.json"

_REQUIRED_OFFER_KEYS = frozenset(
    {"vendor", "price", "category", "title", "url", "valid_until"}
)

_ALL_OFFERS_CACHE: list[OfferDict] | None = None


def _normalize_offer_row(raw: object) -> OfferDict | None:
    """Build a typed offer dict from a JSON object, or None if invalid."""
    if not isinstance(raw, dict):
        return None
    if not _REQUIRED_OFFER_KEYS.issubset(raw.keys()):
        return None
    vendor = raw["vendor"]
    price = raw["price"]
    category = raw["category"]
    title = raw["title"]
    url = raw["url"]
    valid_until = raw["valid_until"]
    if not isinstance(vendor, str) or not isinstance(category, str):
        return None
    if not isinstance(title, str) or not isinstance(url, str):
        return None
    if not isinstance(valid_until, str):
        return None
    if not isinstance(price, (int, float)) or isinstance(price, bool):
        return None
    price_out = int(round(float(price)))
    return {
        "vendor": vendor,
        "price": price_out,
        "category": category,
        "title": title,
        "url": url,
        "valid_until": valid_until,
    }


def load_mock_offers_from_json() -> list[OfferDict]:
    """
    Load all offers from mock_offers.json next to this module.

    Returns an empty list if the file is missing, unreadable, or not valid JSON,
    or if the root value is not a list of well-formed offer objects.
    """
    try:
        text = _OFFERS_JSON.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    offers: list[OfferDict] = []
    for item in data:
        normalized = _normalize_offer_row(item)
        if normalized is not None:
            offers.append(normalized)

    return offers


def _get_all_offers() -> list[OfferDict]:
    """Lazy-load and cache offers from JSON."""
    global _ALL_OFFERS_CACHE
    if _ALL_OFFERS_CACHE is None:
        _ALL_OFFERS_CACHE = load_mock_offers_from_json()
    return _ALL_OFFERS_CACHE


def get_mock_offers(vendor: str) -> list[OfferDict]:
    """Return mock offers for the given vendor (exact name match)."""
    return [o for o in _get_all_offers() if o["vendor"] == vendor]


def _price_distance(offer: OfferDict, predicted_spend: float) -> float:
    """Absolute gap between offer price and predicted spend."""
    return abs(float(offer["price"]) - predicted_spend)


def _parse_valid_until(offer: OfferDict) -> date | None:
    """Parse YYYY-MM-DD from valid_until; None if missing or invalid."""
    raw = offer.get("valid_until")
    if not raw or not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def _offer_is_still_valid(offer: OfferDict, today: date) -> bool:
    """Exclude expired offers; missing or unparseable expiry counts as still valid."""
    expiry = _parse_valid_until(offer)
    if expiry is None:
        return True
    return expiry >= today


def _price_in_spend_band(offer: OfferDict, predicted_spend: float) -> bool:
    """True if price is within ±40% of predicted_spend (0.6x–1.4x)."""
    price = float(offer["price"])
    lo = _PRICE_BAND_LOW * predicted_spend
    hi = _PRICE_BAND_HIGH * predicted_spend
    return lo <= price <= hi


def _category_matches_preference(offer: OfferDict, preferred: str | None) -> bool:
    if not preferred:
        return False
    return str(offer.get("category", "")).strip().lower() == preferred.strip().lower()


def _ranking_key(
    offer: OfferDict,
    predicted_spend: float,
    preferred_category: str | None,
) -> tuple[int, float]:
    """
    Lower is better: prefer category match when preferred_category is set,
    then smaller price distance.
    """
    dist = _price_distance(offer, predicted_spend)
    if not preferred_category:
        return (0, dist)
    cat_ok = _category_matches_preference(offer, preferred_category)
    return (0 if cat_ok else 1, dist)


def _pick_closest(offers: list[OfferDict], predicted_spend: float) -> OfferDict:
    return min(offers, key=lambda o: _price_distance(o, predicted_spend))


def _ranked_offers_for_matching(
    vendor: str,
    predicted_spend: float,
    preferred_category: str | None,
) -> list[OfferDict]:
    """
    All vendor offers in match priority order (best first).

    Tier 1: not expired and in ±40% price band — sorted by category preference, then
    price distance.
    Tier 2: not expired but outside the band — sorted by price distance only.
    Tier 3: expired — sorted by price distance only (fallback).
    """
    offers = get_mock_offers(vendor)
    if not offers:
        return []

    today = date.today()
    p = float(predicted_spend)

    not_expired = [o for o in offers if _offer_is_still_valid(o, today)]
    in_band = [o for o in not_expired if _price_in_spend_band(o, p)]
    not_expired_ids = {id(o) for o in not_expired}
    expired = [o for o in offers if id(o) not in not_expired_ids]

    if in_band:
        tier1 = sorted(
            in_band,
            key=lambda o: _ranking_key(o, p, preferred_category),
        )
        in_band_ids = {id(o) for o in in_band}
        out_of_band_valid = [o for o in not_expired if id(o) not in in_band_ids]
    else:
        tier1 = []
        out_of_band_valid = list(not_expired)

    tier2 = sorted(out_of_band_valid, key=lambda o: _price_distance(o, p))
    tier3 = sorted(expired, key=lambda o: _price_distance(o, p))
    return tier1 + tier2 + tier3


def match_top_offers(
    vendor: str,
    predicted_spend: float,
    preferred_category: str | None = None,
    limit: int = 3,
) -> list[OfferDict]:
    """
    Return up to `limit` offers using the same rules as match_best_offer, ranked
    best-first (in-band and category preference before out-of-band and expired).
    """
    ranked = _ranked_offers_for_matching(vendor, predicted_spend, preferred_category)
    if limit <= 0:
        return []
    return ranked[:limit]


def match_best_offer(
    vendor: str,
    predicted_spend: float,
    preferred_category: str | None = None,
) -> OfferDict | None:
    """
    Pick the best mock offer: filter by validity and price band, rank by category
    preference and closeness to predicted_spend. Falls back to plain closest-price
    if filters remove every candidate.
    """
    top = match_top_offers(vendor, predicted_spend, preferred_category, limit=1)
    return top[0] if top else None


if __name__ == "__main__":
    print(match_top_offers("Walmart", 60, preferred_category="groceries", limit=3))
