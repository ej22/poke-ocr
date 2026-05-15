import base64

from codexocr.vision import image_bytes_from_data_url


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
