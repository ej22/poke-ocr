from __future__ import annotations

from collections import deque

from .database import AppDatabase
from .matcher import CardMatcher
from .models import CardCandidate, CardIdentity, ScanResult
from .normalize import detect_language, normalize_collector_number
from .providers import PriceService, ProviderError


class ScanEngine:
    def __init__(self, database: AppDatabase, stable_frames: int = 3) -> None:
        self.database = database
        self.stable_frames = stable_frames
        self.recent_candidates: deque[CardCandidate] = deque(maxlen=stable_frames)
        self.current = ScanResult(state="idle", message="Waiting for a card.")
        self.paused = False

    def pause(self) -> ScanResult:
        self.paused = True
        self.current = ScanResult(state="paused", message="Scanning paused.")
        return self.current

    def resume(self) -> ScanResult:
        self.paused = False
        self.current = ScanResult(state="identifying", message="Scanning resumed.")
        return self.current

    def ingest_ocr(self, payload: dict[str, object]) -> ScanResult:
        if self.paused:
            return self.current

        candidate = CardCandidate(
            name=_str_or_none(payload.get("name")),
            set_code=_str_or_none(payload.get("set_code")),
            set_name=_str_or_none(payload.get("set_name")),
            collector_number=normalize_collector_number(_str_or_none(payload.get("collector_number"))),
            language=_str_or_none(payload.get("language")) or detect_language(
                _str_or_none(payload.get("name")),
                _str_or_none(payload.get("ocr_text")),
            ),
            confidence=float(payload.get("confidence") or 0.75),
            evidence={"source": payload.get("source") or "manual"},
        )
        self.recent_candidates.append(candidate)

        matcher = CardMatcher(self.database.list_cards())
        identity, score, alternatives = matcher.match(candidate)
        if not identity:
            identity = _identity_from_confident_candidate(candidate)
            score = max(score, candidate.confidence if identity else score)
        candidate = CardCandidate(
            name=candidate.name,
            set_code=candidate.set_code,
            set_name=candidate.set_name,
            collector_number=candidate.collector_number,
            language=candidate.language,
            confidence=round(score, 4),
            evidence={**candidate.evidence, "alternatives": alternatives},
        )

        if not identity:
            best = alternatives[0] if alternatives else None
            detail = (
                f" Best catalog guess: {best['name']} ({best['score']:.2f})."
                if best and isinstance(best.get("score"), float)
                else ""
            )
            self.current = ScanResult(
                state="ambiguous",
                candidate=candidate,
                message=f"OCR did not produce a confident card match yet.{detail}",
            )
            return self.current

        if not self._is_stable(candidate):
            self.current = ScanResult(
                state="identifying",
                candidate=candidate,
                identity=identity,
                message="Waiting for a stable match.",
            )
            return self.current

        try:
            pricing = PriceService(self.database).get_price(identity)
            self.current = ScanResult(
                state="priced",
                candidate=candidate,
                identity=identity,
                price=pricing.snapshot,
                quota=pricing.quota,
                message="Price ready.",
            )
        except ProviderError as exc:
            self.current = ScanResult(
                state="quota_limited" if "quota" in str(exc).lower() else "offline",
                candidate=candidate,
                identity=identity,
                quota=self.database.get_quota("pokewallet"),
                message=str(exc),
            )
        self.database.add_scan_history(self.current.to_dict())
        return self.current

    def _is_stable(self, candidate: CardCandidate) -> bool:
        if len(self.recent_candidates) < self.stable_frames:
            return False
        numbers = {item.collector_number for item in self.recent_candidates}
        names = {item.name for item in self.recent_candidates}
        return len(numbers) == 1 and len(names) == 1 and candidate.confidence >= 0.68


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _identity_from_confident_candidate(candidate: CardCandidate) -> CardIdentity | None:
    if candidate.confidence < 0.9:
        return None
    if not candidate.name or not candidate.set_code or not candidate.collector_number:
        return None
    canonical_id = "manual-" + "-".join(
        part.lower().replace("/", "-").replace(" ", "-")
        for part in [candidate.set_code, candidate.collector_number, candidate.name]
    )
    return CardIdentity(
        canonical_id=canonical_id,
        provider_ids={},
        name=candidate.name,
        set_code=candidate.set_code,
        set_name=candidate.set_name or candidate.set_code,
        collector_number=candidate.collector_number,
        language=candidate.language,
    )
