from codexocr.normalize import detect_language, normalize_card_name, normalize_collector_number


def test_normalize_collector_number_removes_padding_and_ocr_noise():
    assert normalize_collector_number("O20 / 189") == "20/189"
    assert normalize_collector_number("TG05/TG30") == "TG05/TG30"
    assert normalize_collector_number("#004/102") == "4/102"


def test_normalize_collector_number_handles_promos():
    assert normalize_collector_number("SWSH050") == "SWSH050"


def test_detect_language_uses_unicode_scripts():
    assert detect_language("ポケモンカード") == "ja"
    assert detect_language("포켓몬 카드") == "ko"
    assert detect_language("宝可梦") == "zh"


def test_normalize_card_name_folds_accents():
    assert normalize_card_name("Flabébé") == "flabebe"
