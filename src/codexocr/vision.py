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
    if not bounds:
        return VisionResult(
            candidate=CardCandidate(
                name=None,
                set_code=None,
                set_name=None,
                collector_number=None,
                language=detect_language(""),
                confidence=0.35,
                evidence={"source": "webcam", "card_bounds": None},
            ),
            ocr_text="",
            card_bounds=None,
        )

    card = _crop_bounds(image, bounds)
    regions = _ocr_regions(cv2, card)
    region_text = [
        _read_ocr_text(pytesseract, region, config)
        for region, config in (
            (regions[0], "--psm 7 --oem 3"),
            (regions[1], "--psm 7 --oem 3"),
            (regions[2], "--psm 3 --oem 3"),
        )
    ]
    ocr_text = "\n".join(region_text).strip()
    candidate = _candidate_from_text(ocr_text, bottom_text=region_text[1])
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
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) != 4:
            continue
        area = cv2.contourArea(polygon)
        if area <= image_area * 0.08:
            continue
        x, y, width, height = cv2.boundingRect(polygon)
        aspect = height / max(width, 1)
        if 1.35 <= aspect <= 1.45:
            aspect_delta = abs(aspect - 1.4)
            candidates.append((area, -aspect_delta, (x, y, width, height)))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def _crop_bounds(image, bounds: tuple[int, int, int, int]):
    x, y, width, height = bounds
    return image[y : y + height, x : x + width]


def _ocr_regions(cv2, card):
    height, width = card.shape[:2]
    top = card[0 : int(height * 0.22), 0:width]
    bottom = card[int(height * 0.68) : height, 0:width]
    return [_preprocess_region(cv2, region) for region in (top, bottom, card)]


def _preprocess_region(cv2, image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    upscaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    thresholded = cv2.adaptiveThreshold(
        upscaled,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        10,
    )
    sharpen_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)).astype("float32") * -1
    sharpen_kernel[1, 1] = 9
    return cv2.filter2D(thresholded, -1, sharpen_kernel)


def _read_ocr_text(pytesseract, region, config: str = "") -> str:
    try:
        if config:
            return pytesseract.image_to_string(region, config=config)
        return pytesseract.image_to_string(region)
    except Exception as exc:
        if exc.__class__.__name__ == "TesseractNotFoundError":
            raise VisionUnavailable(
                "Tesseract OCR is not installed or is not on PATH. Install Tesseract for Windows, "
                "then restart this app."
            ) from exc
        raise


def _candidate_from_text(text: str, bottom_text: str = "") -> CardCandidate:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name_line = next((line for line in lines if _is_possible_card_name(line)), None)
    name = normalize_card_name(name_line) if name_line else None
    collector_number = normalize_collector_number(text)
    set_code = _extract_set_code(bottom_text)
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
    false_positives = {"HP", "GX", "EX", "VMAX", "VSTAR", "TAG", "TEAM", "FULL", "CARD", "ART", "ITEM", "TOOL"}
    for match in re.finditer(r"\b([A-Z0-9]{2,6})\b", text.upper()):
        code = match.group(1)
        if code in false_positives or code.isdigit():
            continue
        return code
    return None


def _is_possible_card_name(line: str) -> bool:
    normalized = line.strip()
    if len(normalized) < 2 or normalized.isdigit():
        return False
    upper = normalized.upper()
    if upper in {"HP", "GX", "EX", "VMAX", "VSTAR"}:
        return False
    if re.fullmatch(r"\d+\s*HP|HP\s*\d+|\d+", upper):
        return False
    return True
