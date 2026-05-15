from __future__ import annotations

import base64
import re
from dataclasses import dataclass

from .models import CardCandidate
from .normalize import detect_language, normalize_card_name, normalize_collector_number


class VisionUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class VisionResult:
    candidate: CardCandidate
    ocr_text: str
    card_bounds: tuple[int, int, int, int] | None


def image_bytes_from_data_url(data_url: str) -> bytes:
    match = re.match(r"^data:image/[a-zA-Z0-9.+-]+;base64,(?P<body>.+)$", data_url)
    if not match:
        raise ValueError("Expected a base64 image data URL.")
    return base64.b64decode(match.group("body"), validate=True)


def analyze_frame_data_url(data_url: str) -> VisionResult:
    image_bytes = image_bytes_from_data_url(data_url)
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        import pytesseract  # type: ignore
    except ImportError as exc:
        raise VisionUnavailable("Install the vision extra to enable webcam OCR: pip install -e '.[vision]'") from exc

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode webcam frame.")

    bounds = _find_card_bounds(cv2, image)
    card = _crop_bounds(image, bounds) if bounds else image
    regions = _ocr_regions(card)
    ocr_text = _read_ocr_text(pytesseract, regions)
    candidate = _candidate_from_text(ocr_text)
    if bounds:
        candidate = CardCandidate(
            name=candidate.name,
            set_code=candidate.set_code,
            set_name=candidate.set_name,
            collector_number=candidate.collector_number,
            language=candidate.language,
            confidence=max(candidate.confidence, 0.62),
            evidence={**candidate.evidence, "card_bounds": bounds, "source": "webcam"},
        )
    return VisionResult(candidate=candidate, ocr_text=ocr_text, card_bounds=bounds)


def _find_card_bounds(cv2, image) -> tuple[int, int, int, int] | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 60, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    image_area = image.shape[0] * image.shape[1]
    candidates = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = width * height
        aspect = height / max(width, 1)
        if area > image_area * 0.08 and 1.15 <= aspect <= 1.65:
            candidates.append((area, (x, y, width, height)))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _crop_bounds(image, bounds: tuple[int, int, int, int]):
    x, y, width, height = bounds
    return image[y : y + height, x : x + width]


def _ocr_regions(card):
    height, width = card.shape[:2]
    top = card[0 : int(height * 0.22), 0:width]
    bottom = card[int(height * 0.68) : height, 0:width]
    return [top, bottom, card]


def _read_ocr_text(pytesseract, regions) -> str:
    try:
        return "\n".join(pytesseract.image_to_string(region) for region in regions).strip()
    except Exception as exc:
        if exc.__class__.__name__ == "TesseractNotFoundError":
            raise VisionUnavailable(
                "Tesseract OCR is not installed or is not on PATH. Install Tesseract for Windows, "
                "then restart this app."
            ) from exc
        raise


def _candidate_from_text(text: str) -> CardCandidate:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name = normalize_card_name(lines[0]) if lines else None
    collector_number = normalize_collector_number(text)
    set_code = _extract_set_code(text)
    confidence = 0.45
    if name:
        confidence += 0.12
    if collector_number:
        confidence += 0.18
    if set_code:
        confidence += 0.08
    return CardCandidate(
        name=name.title() if name else None,
        set_code=set_code,
        set_name=None,
        collector_number=collector_number,
        language=detect_language(text),
        confidence=min(confidence, 0.86),
        evidence={"source": "ocr", "raw_text": text[:1000]},
    )


def _extract_set_code(text: str) -> str | None:
    match = re.search(r"\b([A-Z]{2,5}\d?)\b", text.upper())
    return match.group(1) if match else None
