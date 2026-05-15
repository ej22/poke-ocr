from __future__ import annotations

from difflib import SequenceMatcher

from .models import CardCandidate, CardIdentity
from .normalize import fold_text, normalize_card_name, normalize_collector_number


def score_candidate(candidate: CardCandidate, identity: CardIdentity) -> float:
    score = 0.0
    normalized_number = normalize_collector_number(candidate.collector_number)
    if normalized_number and normalized_number == normalize_collector_number(identity.collector_number):
        score += 0.46
    if candidate.set_code and fold_text(candidate.set_code) == fold_text(identity.set_code):
        score += 0.2
    elif candidate.set_name and fold_text(candidate.set_name) == fold_text(identity.set_name):
        score += 0.16
    if candidate.language == identity.language:
        score += 0.08
    candidate_name = normalize_card_name(candidate.name)
    identity_name = normalize_card_name(identity.name)
    if candidate_name and identity_name:
        score += 0.26 * SequenceMatcher(None, candidate_name, identity_name).ratio()
    return min(1.0, round(score * max(candidate.confidence, 0.25), 4))


class CardMatcher:
    def __init__(self, cards: list[CardIdentity]) -> None:
        self.cards = cards

    def match(self, candidate: CardCandidate) -> tuple[CardIdentity | None, float, list[dict[str, float | str]]]:
        scored = sorted(
            ((identity, score_candidate(candidate, identity)) for identity in self.cards),
            key=lambda item: item[1],
            reverse=True,
        )
        alternatives = [
            {"canonical_id": identity.canonical_id, "name": identity.name, "score": score}
            for identity, score in scored[:5]
        ]
        if not scored or scored[0][1] < 0.55:
            return None, scored[0][1] if scored else 0.0, alternatives
        return scored[0][0], scored[0][1], alternatives
