import base64

from codexocr.vision import VisionUnavailable, image_bytes_from_data_url, _read_ocr_text


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
        _read_ocr_text(FakePytesseract(), ["region"])
    except VisionUnavailable as exc:
        assert "Tesseract OCR" in str(exc)
    else:
        raise AssertionError("Expected missing Tesseract to be reported as unavailable vision support")
