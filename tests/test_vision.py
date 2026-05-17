import base64

from codexocr.vision import (
    VisionUnavailable,
    _candidate_from_text,
    _extract_set_code,
    _find_card_bounds,
    _preprocess_region,
    _read_ocr_text,
    image_bytes_from_data_url,
)


def test_image_bytes_from_data_url_decodes_base64_image():
    payload = base64.b64encode(b"fake-image").decode("ascii")
    assert image_bytes_from_data_url(f"data:image/jpeg;base64,{payload}") == b"fake-image"


def test_image_bytes_from_data_url_rejects_plain_base64():
    try:
        image_bytes_from_data_url(base64.b64encode(b"fake-image").decode("ascii"))
    except ValueError as exc:
        assert "data URL" in str(exc)
    else:
        raise AssertionError("Expected invalid data URL to fail")


def test_read_ocr_text_reports_missing_tesseract():
    class TesseractNotFoundError(RuntimeError):
        pass

    class FakePytesseract:
        @staticmethod
        def image_to_string(region):
            raise TesseractNotFoundError()

    try:
        _read_ocr_text(FakePytesseract(), "region")
    except VisionUnavailable as exc:
        assert "Tesseract OCR" in str(exc)
    else:
        raise AssertionError("Expected missing Tesseract to be reported as unavailable vision support")


def test_preprocess_region_returns_expected_array_shape():
    deps = _vision_deps()
    if deps is None:
        return
    cv2, np = deps
    image = np.zeros((24, 32, 3), dtype=np.uint8)

    processed = _preprocess_region(cv2, image)

    assert processed.shape == (48, 64)
    assert processed.dtype == np.uint8


def test_extract_set_code_filters_known_false_positives():
    assert _extract_set_code("HP GX EX VMAX VSTAR TAG TEAM FULL CARD ART ITEM TOOL") is None
    assert _extract_set_code("120 090") is None
    assert _extract_set_code("123/189 SV1 EN") == "SV1"


def test_candidate_from_text_skips_noise_lines_for_name():
    candidate = _candidate_from_text("HP\n120\nVMAX\nPikachu\n123/189", bottom_text="SV1 123/189")

    assert candidate.name == "Pikachu"
    assert candidate.set_code == "SV1"


def test_find_card_bounds_returns_none_without_card_contour():
    deps = _vision_deps()
    if deps is None:
        return
    cv2, np = deps
    image = np.zeros((200, 200, 3), dtype=np.uint8)

    assert _find_card_bounds(cv2, image) is None


def _vision_deps():
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None
    return cv2, np
