from __future__ import annotations

import json
import sqlite3
from threading import RLock
from pathlib import Path
from typing import Any

from .models import CardIdentity, PriceSnapshot, QuotaState, utc_now_iso
from .sample_catalog import SAMPLE_CARDS

DEFAULT_DATA_DIR = Path("data")
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "codexocr.sqlite"


class AppDatabase:
    def __init__(self, path: Path | str = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.migrate()

    def close(self) -> None:
        with self.lock:
            self.connection.close()

    def migrate(self) -> None:
        with self.lock:
            self.connection.executescript(
                """
                create table if not exists settings (
                    key text primary key,
                    value text not null,
                    updated_at text not null
                );

                create table if not exists cards (
                    canonical_id text primary key,
                    provider_ids text not null,
                    name text not null,
                    set_code text not null,
                    set_name text not null,
                    collector_number text not null,
                    language text not null,
                    variant text not null default 'raw',
                    image_url text
                );

                create table if not exists price_cache (
                    cache_key text primary key,
                    payload text not null,
                    fetched_at text not null
                );

                create table if not exists quota_state (
                    provider text primary key,
                    payload text not null,
                    updated_at text not null
                );

                create table if not exists scan_history (
                    id integer primary key autoincrement,
                    payload text not null,
                    created_at text not null
                );
                """
            )
            self.connection.commit()
        self.seed_sample_cards()

    def seed_sample_cards(self) -> None:
        for card in SAMPLE_CARDS:
            identity = CardIdentity(
                canonical_id=card["canonical_id"],
                provider_ids={"pokewallet": card["pokewallet_id"]},
                name=card["name"],
                set_code=card["set_code"],
                set_name=card["set_name"],
                collector_number=card["collector_number"],
                language=card["language"],
                image_url=card["image_url"],
            )
            self.upsert_card(identity)

    def set_setting(self, key: str, value: Any) -> None:
        with self.lock:
            self.connection.execute(
                """
                insert into settings (key, value, updated_at) values (?, ?, ?)
                on conflict(key) do update set value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, json.dumps(value), utc_now_iso()),
            )
            self.connection.commit()

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.lock:
            row = self.connection.execute("select value from settings where key = ?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def upsert_card(self, identity: CardIdentity) -> None:
        with self.lock:
            self.connection.execute(
                """
                insert into cards (
                    canonical_id, provider_ids, name, set_code, set_name,
                    collector_number, language, variant, image_url
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(canonical_id) do update set
                    provider_ids = excluded.provider_ids,
                    name = excluded.name,
                    set_code = excluded.set_code,
                    set_name = excluded.set_name,
                    collector_number = excluded.collector_number,
                    language = excluded.language,
                    variant = excluded.variant,
                    image_url = excluded.image_url
                """,
                (
                    identity.canonical_id,
                    json.dumps(identity.provider_ids),
                    identity.name,
                    identity.set_code,
                    identity.set_name,
                    identity.collector_number,
                    identity.language,
                    identity.variant,
                    identity.image_url,
                ),
            )
            self.connection.commit()

    def list_cards(self) -> list[CardIdentity]:
        with self.lock:
            rows = self.connection.execute("select * from cards order by name").fetchall()
        return [self._row_to_identity(row) for row in rows]

    def get_card(self, canonical_id: str) -> CardIdentity | None:
        with self.lock:
            row = self.connection.execute("select * from cards where canonical_id = ?", (canonical_id,)).fetchone()
        return self._row_to_identity(row) if row else None

    def get_cached_price(self, cache_key: str) -> PriceSnapshot | None:
        with self.lock:
            row = self.connection.execute("select payload from price_cache where cache_key = ?", (cache_key,)).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload"])
        payload["cache_status"] = "cache"
        return PriceSnapshot(**payload)

    def cache_price(self, cache_key: str, snapshot: PriceSnapshot) -> None:
        with self.lock:
            self.connection.execute(
                """
                insert into price_cache (cache_key, payload, fetched_at) values (?, ?, ?)
                on conflict(cache_key) do update set payload = excluded.payload, fetched_at = excluded.fetched_at
                """,
                (cache_key, json.dumps(snapshot.to_dict()), snapshot.fetched_at),
            )
            self.connection.commit()

    def get_quota(self, provider: str) -> QuotaState | None:
        with self.lock:
            row = self.connection.execute("select payload from quota_state where provider = ?", (provider,)).fetchone()
        return QuotaState(**json.loads(row["payload"])) if row else None

    def set_quota(self, quota: QuotaState) -> None:
        with self.lock:
            self.connection.execute(
                """
                insert into quota_state (provider, payload, updated_at) values (?, ?, ?)
                on conflict(provider) do update set payload = excluded.payload, updated_at = excluded.updated_at
                """,
                (quota.provider, json.dumps(quota.to_dict()), utc_now_iso()),
            )
            self.connection.commit()

    def add_scan_history(self, payload: dict[str, Any]) -> None:
        with self.lock:
            self.connection.execute(
                "insert into scan_history (payload, created_at) values (?, ?)",
                (json.dumps(payload), utc_now_iso()),
            )
            self.connection.commit()

    def _row_to_identity(self, row: sqlite3.Row) -> CardIdentity:
        return CardIdentity(
            canonical_id=row["canonical_id"],
            provider_ids=json.loads(row["provider_ids"]),
            name=row["name"],
            set_code=row["set_code"],
            set_name=row["set_name"],
            collector_number=row["collector_number"],
            language=row["language"],
            variant=row["variant"],
            image_url=row["image_url"],
        )
