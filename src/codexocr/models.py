from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class CardCandidate:
    name: str | None
    set_code: str | None
    set_name: str | None
    collector_number: str | None
    language: str
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CardIdentity:
    canonical_id: str
    provider_ids: dict[str, str]
    name: str
    set_code: str
    set_name: str
    collector_number: str
    language: str
    variant: str = "raw"
    image_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PriceSnapshot:
    market: float | None
    low: float | None
    mid: float | None
    high: float | None
    currency: str
    provider: str
    variant: str
    fetched_at: str
    cache_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QuotaState:
    provider: str
    hourly_limit: int | None = None
    hourly_remaining: int | None = None
    daily_limit: int | None = None
    daily_remaining: int | None = None
    reset_estimate: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScanResult:
    state: str
    candidate: CardCandidate | None = None
    identity: CardIdentity | None = None
    price: PriceSnapshot | None = None
    quota: QuotaState | None = None
    message: str | None = None
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "candidate": self.candidate.to_dict() if self.candidate else None,
            "identity": self.identity.to_dict() if self.identity else None,
            "price": self.price.to_dict() if self.price else None,
            "quota": self.quota.to_dict() if self.quota else None,
            "message": self.message,
            "updated_at": self.updated_at,
        }
