from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
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

    def __init__(self, api_key: str | None = None, base_url: str = "https://www.pokewallet.io/api") -> None:
        self.api_key = api_key or os.getenv("POKEWALLET_API_KEY")
        self.base_url = base_url.rstrip("/")

    def fetch_price(self, identity: CardIdentity) -> PricingResult:
        if not self.api_key:
            raise ProviderError("PokéWallet API key is not configured.")
        provider_id = identity.provider_ids.get("pokewallet")
        if not provider_id:
            raise ProviderError(f"No PokéWallet provider id for {identity.canonical_id}.")

        request = Request(
            f"{self.base_url}/cards/{provider_id}",
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=8) as response:
                body = json.loads(response.read().decode("utf-8"))
                quota = self._quota_from_headers(response.headers)
        except HTTPError as exc:
            if exc.code == 429:
                raise ProviderError("PokéWallet quota limit reached.") from exc
            raise ProviderError(f"PokéWallet returned HTTP {exc.code}.") from exc
        except URLError as exc:
            raise ProviderError(f"PokéWallet request failed: {exc.reason}") from exc

        price = body.get("price") or body.get("prices") or body
        snapshot = PriceSnapshot(
            market=_as_float(price.get("market") or price.get("marketPrice") or price.get("value")),
            low=_as_float(price.get("low")),
            mid=_as_float(price.get("mid") or price.get("average")),
            high=_as_float(price.get("high")),
            currency=price.get("currency") or "USD",
            provider=self.provider_name,
            variant=identity.variant,
            fetched_at=datetime.now(UTC).isoformat(),
            cache_status="live",
        )
        return PricingResult(snapshot=snapshot, quota=quota)

    def _quota_from_headers(self, headers: Any) -> QuotaState:
        return QuotaState(
            provider=self.provider_name,
            hourly_limit=_as_int(headers.get("X-RateLimit-Hour-Limit")),
            hourly_remaining=_as_int(headers.get("X-RateLimit-Hour-Remaining")),
            daily_limit=_as_int(headers.get("X-RateLimit-Day-Limit")),
            daily_remaining=_as_int(headers.get("X-RateLimit-Day-Remaining")),
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
        result = self.provider.fetch_price(identity)
        self.database.cache_price(cache_key, result.snapshot)
        if result.quota:
            self.database.set_quota(result.quota)
        return result


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
