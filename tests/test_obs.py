from codexocr.obs import build_browser_source_config


def test_build_browser_source_config_uses_local_overlay_url():
    config = build_browser_source_config(host="localhost", port=9000)

    assert config.name == "CodexOCR Card Price Overlay"
    assert config.url == "http://localhost:9000/overlay"
    assert config.transparent is True
    assert config.width == 1920
    assert config.height == 1080
