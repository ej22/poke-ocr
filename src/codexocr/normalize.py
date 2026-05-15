from __future__ import annotations

import re
import unicodedata

LANGUAGE_HINTS = {
    "en": ("pokemon", "trainer", "basic", "stage", "energy"),
    "de": ("entwickelt", "trainerkarte", "basis", "kampf"),
    "fr": ("evolution", "dresseur", "base", "energie"),
    "es": ("evoluciona", "entrenador", "basico", "energia"),
    "it": ("evoluzione", "allenatore", "base", "energia"),
    "pt": ("evolui", "treinador", "basico", "energia"),
    "ja": ("ポケモン", "トレーナーズ", "進化"),
    "ko": ("포켓몬", "트레이너스"),
    "zh": ("寶可夢", "宝可梦", "训练家"),
}


def fold_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    asciiish = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", asciiish).strip().lower()


def normalize_collector_number(value: str | None) -> str | None:
    if not value:
        return None
    text = value.upper().replace("O", "0").replace(" ", "")
    text = text.replace("\\", "/").replace("|", "/")
    text = re.sub(r"[^A-Z0-9/#-]", "", text)
    match = re.search(r"([A-Z]{0,4}\d{1,3}[A-Z]?)(?:/([A-Z]{0,4}\d{1,3}))?", text)
    if not match:
        return None
    left = match.group(1).lstrip("0") or "0"
    right = match.group(2)
    if right:
        right = right.lstrip("0") or "0"
        return f"{left}/{right}"
    return left


def detect_language(*texts: str | None) -> str:
    combined_raw = " ".join(text for text in texts if text)
    if re.search(r"[\u3040-\u30ff]", combined_raw):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", combined_raw):
        return "ko"
    if re.search(r"[\u4e00-\u9fff]", combined_raw):
        return "zh"
    combined = fold_text(combined_raw)
    scores = {
        code: sum(1 for hint in hints if hint in combined)
        for code, hints in LANGUAGE_HINTS.items()
        if code not in {"ja", "ko", "zh"}
    }
    best = max(scores.items(), key=lambda item: item[1], default=("en", 0))
    return best[0] if best[1] > 0 else "en"


def normalize_card_name(value: str | None) -> str | None:
    text = fold_text(value)
    if not text:
        return None
    text = re.sub(r"[^a-z0-9 .:'-]", "", text)
    return re.sub(r"\s+", " ", text).strip() or None
