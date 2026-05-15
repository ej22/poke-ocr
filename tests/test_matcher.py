from codexocr.matcher import CardMatcher
from codexocr.models import CardCandidate, CardIdentity
from codexocr.database import AppDatabase
from codexocr.scanner import ScanEngine


def test_matcher_finds_card_by_number_set_and_name():
    identity = CardIdentity(
        canonical_id="swsh3-020",
        provider_ids={"pokewallet": "pk_sample"},
        name="Charizard VMAX",
        set_code="SWSH3",
        set_name="Darkness Ablaze",
        collector_number="20/189",
        language="en",
    )
    candidate = CardCandidate(
        name="Charizard VMAX",
        set_code="SWSH3",
        set_name=None,
        collector_number="020/189",
        language="en",
        confidence=0.95,
    )
    match, score, alternatives = CardMatcher([identity]).match(candidate)

    assert match == identity
    assert score > 0.8
    assert alternatives[0]["canonical_id"] == "swsh3-020"


def test_matcher_rejects_low_confidence_candidate():
    identity = CardIdentity(
        canonical_id="base1-004",
        provider_ids={"pokewallet": "pk_sample"},
        name="Charizard",
        set_code="BASE1",
        set_name="Base Set",
        collector_number="4/102",
        language="en",
    )
    candidate = CardCandidate(
        name="Unknown",
        set_code=None,
        set_name=None,
        collector_number=None,
        language="en",
        confidence=0.3,
    )
    match, score, _ = CardMatcher([identity]).match(candidate)

    assert match is None
    assert score < 0.55


def test_scanner_ambiguous_message_includes_best_guess(tmp_path):
    database = AppDatabase(tmp_path / "test.sqlite")
    scanner = ScanEngine(database)

    result = scanner.ingest_ocr(
        {
            "name": "Charizard",
            "set_code": None,
            "collector_number": None,
            "language": "en",
            "confidence": 0.3,
        }
    )

    assert result.state == "ambiguous"
    assert "OCR did not produce" in result.message
    assert "Best catalog guess" in result.message


def test_scanner_uses_confident_manual_candidate_when_catalog_lacks_card(tmp_path):
    database = AppDatabase(tmp_path / "test.sqlite")
    scanner = ScanEngine(database)

    result = scanner.ingest_ocr(
        {
            "name": "Aurorus",
            "set_code": "POR",
            "collector_number": "024/088",
            "language": "en",
            "confidence": 0.95,
            "source": "manual",
        }
    )

    assert result.state == "identifying"
    assert result.identity.name == "Aurorus"
    assert result.identity.set_code == "POR"
    assert result.identity.collector_number == "24/88"
