from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .database import AppDatabase
from .models import CardIdentity


class CatalogError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyncSummary:
    imported: int
    pages: int


class PokemonTcgCatalogClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.pokemontcg.io/v2") -> None:
        self.api_key = api_key or os.getenv("POKEMONTCG_API_KEY")
        self.base_url = base_url.rstrip("/")

    def iter_cards(self, query: str | None = None, max_pages: int = 1, page_size: int = 250) -> Iterator[dict]:
        for page in range(1, max_pages + 1):
            params = {"page": page, "pageSize": page_size}
            if query:
                params["q"] = query
            request = Request(
                f"{self.base_url}/cards?{urlencode(params)}",
                headers=self._headers(),
            )
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            for card in payload.get("data", []):
                yield card
            if len(payload.get("data", [])) < page_size:
                break

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        return headers


def sync_pokemon_tcg_catalog(
    database: AppDatabase,
    client: PokemonTcgCatalogClient | None = None,
    query: str | None = None,
    max_pages: int = 1,
) -> SyncSummary:
    client = client or PokemonTcgCatalogClient(database.get_setting("pokemontcg_api_key"))
    imported = 0
    pages_seen = 0
    try:
        for card in client.iter_cards(query=query, max_pages=max_pages):
            identity = identity_from_pokemon_tcg_card(card)
            if identity:
                database.upsert_card(identity)
                imported += 1
            pages_seen = max(1, (imported // 250) + 1)
    except OSError as exc:
        raise CatalogError(f"Pokemon TCG catalog sync failed: {exc}") from exc
    return SyncSummary(imported=imported, pages=min(max_pages, pages_seen))


def identity_from_pokemon_tcg_card(card: dict) -> CardIdentity | None:
    set_info = card.get("set") or {}
    images = card.get("images") or {}
    card_id = card.get("id")
    name = card.get("name")
    number = card.get("number")
    set_code = set_info.get("id") or set_info.get("ptcgoCode")
    set_name = set_info.get("name")
    if not all([card_id, name, number, set_code, set_name]):
        return None
    printed_total = set_info.get("printedTotal") or set_info.get("total")
    collector_number = f"{number}/{printed_total}" if printed_total and "/" not in str(number) else str(number)
    return CardIdentity(
        canonical_id=str(card_id),
        provider_ids={"pokemon_tcg": str(card_id)},
        name=str(name),
        set_code=str(set_code).upper(),
        set_name=str(set_name),
        collector_number=collector_number,
        language="en",
        image_url=images.get("large") or images.get("small"),
    )
