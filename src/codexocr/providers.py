from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .database import AppDatabase
from .models import CardIdentity, PriceSnapshot, QuotaState


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class PricingResult:
    snapshot: PriceSnapshot
    quota: QuotaState | None


class PokewalletProvider:
    provider_name = "pokewallet"

    def __init__(self, api_key: str | None = None, base_url: str = "https://api.pokewallet.io") -> None:
        self.api_key = api_key or os.getenv("POKEWALLET_API_KEY")
        self.base_url = base_url.rstrip("/")

    def fetch_price(self, identity: CardIdentity) -> PricingResult:
        if not self.api_key:
            raise ProviderError("PokeWallet API key is not configured.")

        body, quota = self._fetch_price_body(identity)
        price = _best_price(body)
        snapshot = PriceSnapshot(
            market=_as_float(price.get("market") or price.get("market_price") or price.get("value") or price.get("avg")),
            low=_as_float(price.get("low") or price.get("low_price")),
            mid=_as_float(price.get("mid") or price.get("mid_price") or price.get("average") or price.get("avg7")),
            high=_as_float(price.get("high") or price.get("high_price")),
            currency=price.get("currency") or ("EUR" if price.get("variant_type") else "USD"),
            provider=self.provider_name,
            variant=identity.variant,
            fetched_at=datetime.now(UTC).isoformat(),
            cache_status="live",
        )
        return PricingResult(snapshot=snapshot, quota=quota)

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.api_key or "",
            "Accept": "application/json",
            "User-Agent": "CodexOCR/0.1 Python API Client",
        }

    def _fetch_price_body(self, identity: CardIdentity) -> tuple[dict[str, Any], QuotaState]:
        provider_id = identity.provider_ids.get("pokewallet")
        if provider_id and not provider_id.startswith("pk_sample"):
            return self._get_card(provider_id)

        cards, quota = self._search_for_matching_cards(identity)
        match = _find_matching_card(cards, identity)
        if not match:
            summary = _summarize_cards(cards)
            detail = f" Returned: {summary}." if summary else ""
            raise ProviderError(f"No PokeWallet search result matched {identity.name} {identity.collector_number}.{detail}")
        return match, quota

    def _search_for_matching_cards(self, identity: CardIdentity) -> tuple[list[dict[str, Any]], QuotaState]:
        quota = QuotaState(provider=self.provider_name)
        all_cards: list[dict[str, Any]] = []
        for query in _search_queries(identity):
            payload, quota = self._search_cards(query)
            cards = _cards_from_search(payload)
            all_cards.extend(card for card in cards if card.get("id") not in {item.get("id") for item in all_cards})
            if _find_matching_card(cards, identity):
                return cards, quota
        return all_cards, quota

    def _search_cards(self, query: str) -> tuple[dict[str, Any], QuotaState]:
        request = Request(
            f"{self.base_url}/search?{urlencode({'q': query, 'limit': 10})}",
            headers=self._headers(),
        )
        try:
            with urlopen(request, timeout=8) as response:
                return json.loads(response.read().decode("utf-8")), self._quota_from_headers(response.headers)
        except HTTPError as exc:
            raise _provider_error_from_http("search", exc) from exc
        except URLError as exc:
            raise ProviderError(f"PokeWallet search failed: {exc.reason}") from exc

    def _get_card(self, provider_id: str) -> tuple[dict[str, Any], QuotaState]:
        request = Request(f"{self.base_url}/cards/{provider_id}", headers=self._headers())
        try:
            with urlopen(request, timeout=8) as response:
                return json.loads(response.read().decode("utf-8")), self._quota_from_headers(response.headers)
        except HTTPError as exc:
            raise _provider_error_from_http("card lookup", exc) from exc
        except URLError as exc:
            raise ProviderError(f"PokeWallet card lookup failed: {exc.reason}") from exc

    def _quota_from_headers(self, headers: Any) -> QuotaState:
        return QuotaState(
            provider=self.provider_name,
            hourly_limit=_as_int(headers.get("X-RateLimit-Hour-Limit") or headers.get("X-RateLimit-Limit-Hour")),
            hourly_remaining=_as_int(
                headers.get("X-RateLimit-Hour-Remaining") or headers.get("X-RateLimit-Remaining-Hour")
            ),
            daily_limit=_as_int(headers.get("X-RateLimit-Day-Limit") or headers.get("X-RateLimit-Limit-Day")),
            daily_remaining=_as_int(
                headers.get("X-RateLimit-Day-Remaining") or headers.get("X-RateLimit-Remaining-Day")
            ),
            reset_estimate=headers.get("X-RateLimit-Reset"),
        )


class PriceService:
    def __init__(self, database: AppDatabase, provider: PokewalletProvider | None = None) -> None:
        self.database = database
        self.provider = provider or PokewalletProvider(database.get_setting("pokewallet_api_key"))

    def get_price(self, identity: CardIdentity) -> PricingResult:
        cache_key = f"{self.provider.provider_name}:{identity.canonical_id}:{identity.variant}:{identity.language}"
        cached = self.database.get_cached_price(cache_key)
        quota = self.database.get_quota(self.provider.provider_name)
        if cached:
            return PricingResult(snapshot=cached, quota=quota)
        if quota and (quota.hourly_remaining == 0 or quota.daily_remaining == 0):
            raise ProviderError("PokeWallet quota limit reached; using cached prices only.")
        result = self.provider.fetch_price(identity)
        self.database.cache_price(cache_key, result.snapshot)
        if result.quota:
            self.database.set_quota(result.quota)
        return result


def _provider_error_from_http(context: str, exc: HTTPError) -> ProviderError:
    message = _error_message_from_http(exc)
    if exc.code == 429:
        return ProviderError("PokeWallet quota limit reached.")
    if exc.code in {401, 403}:
        return ProviderError(f"PokeWallet {context} was rejected with HTTP {exc.code}: {message}")
    return ProviderError(f"PokeWallet {context} returned HTTP {exc.code}: {message}")


def _error_message_from_http(exc: HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8")
    except Exception:
        return exc.reason or "No response body."
    if not body:
        return exc.reason or "No response body."
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body[:300]
    message = payload.get("message") or payload.get("detail") or payload.get("error")
    title = payload.get("title")
    if title and message:
        return f"{title}: {message}"[:300]
    return str(message or payload)[:300]


def _cards_from_search(payload: dict[str, Any]) -> list[dict[str, Any]]:
    cards = payload.get("results")
    if cards is None:
        cards = payload.get("data")
    return cards if isinstance(cards, list) else []


def _search_queries(identity: CardIdentity) -> list[str]:
    number = identity.collector_number.split("/")[0]
    candidates = [
        " ".join(part for part in [identity.name, identity.set_code, number] if part),
        " ".join(part for part in [identity.name, identity.set_code] if part),
        " ".join(part for part in [identity.name, identity.collector_number] if part),
        identity.name,
        " ".join(part for part in [identity.set_code, number] if part),
    ]
    queries: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in queries:
            queries.append(candidate)
    return queries


def _find_matching_card(cards: list[dict[str, Any]], identity: CardIdentity) -> dict[str, Any] | None:
    scored = sorted(
        ((card, _search_result_score(card.get("card_info") or {}, identity)) for card in cards),
        key=lambda item: item[1],
        reverse=True,
    )
    for card, score in scored:
        if score >= 0.62:
            return card
    return scored[0][0] if scored and scored[0][1] >= 0.48 else None


def _search_result_score(card_info: dict[str, Any], identity: CardIdentity) -> float:
    score = 0.0
    number = str(card_info.get("card_number") or "").split("/")[0].lstrip("0")
    identity_number = identity.collector_number.split("/")[0].lstrip("0")
    if number and identity_number and number == identity_number:
        score += 0.35
    set_code = str(card_info.get("set_code") or "").upper()
    if set_code and set_code == identity.set_code.upper():
        score += 0.25
    name = str(card_info.get("clean_name") or card_info.get("name") or "").lower()
    if name:
        score += 0.4 * SequenceMatcher(None, identity.name.lower(), name).ratio()
    return score


def _summarize_cards(cards: list[dict[str, Any]]) -> str:
    summaries = []
    for card in cards:
        card_info = card.get("card_info") or {}
        name = card_info.get("clean_name") or card_info.get("name") or "unknown"
        set_code = card_info.get("set_code") or "unknown set"
        number = card_info.get("card_number") or "unknown number"
        summaries.append(f"{name} ({set_code} {number})")
    return "; ".join(summaries[:3])


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _best_price(body: dict[str, Any]) -> dict[str, Any]:
    if isinstance(body.get("price"), dict):
        return body["price"]
    if isinstance(body.get("prices"), dict):
        return body["prices"]
    tcg_prices = ((body.get("tcgplayer") or {}).get("prices") or [])
    if tcg_prices:
        return tcg_prices[0]
    cardmarket_prices = ((body.get("cardmarket") or {}).get("prices") or [])
    if cardmarket_prices:
        return cardmarket_prices[0]
    return body


def _matches_identity(card_info: dict[str, Any], identity: CardIdentity) -> bool:
    number = str(card_info.get("card_number") or "").split("/")[0]
    identity_number = identity.collector_number.split("/")[0]
    set_code = str(card_info.get("set_code") or "").upper()
    name = str(card_info.get("clean_name") or card_info.get("name") or "").lower()
    return number == identity_number and set_code == identity.set_code.upper() and identity.name.lower() in name
