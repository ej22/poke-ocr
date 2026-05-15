from codexocr.database import AppDatabase
from codexocr.models import CardIdentity, PriceSnapshot, QuotaState
from codexocr.providers import PokewalletProvider, PriceService, PricingResult, ProviderError, _provider_error_from_http
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO


class FakeProvider:
    provider_name = "pokewallet"

    def __init__(self):
        self.calls = 0

    def fetch_price(self, identity):
        self.calls += 1
        return PricingResult(
            snapshot=PriceSnapshot(
                market=42.5,
                low=35,
                mid=41,
                high=55,
                currency="USD",
                provider="pokewallet",
                variant=identity.variant,
                fetched_at="2026-05-15T00:00:00+00:00",
                cache_status="live",
            ),
            quota=QuotaState(
                provider="pokewallet",
                hourly_limit=100,
                hourly_remaining=99,
                daily_limit=1000,
                daily_remaining=999,
            ),
        )


def test_price_service_caches_provider_results(tmp_path):
    database = AppDatabase(tmp_path / "test.sqlite")
    identity = CardIdentity(
        canonical_id="swsh3-020",
        provider_ids={"pokewallet": "pk_sample"},
        name="Charizard VMAX",
        set_code="SWSH3",
        set_name="Darkness Ablaze",
        collector_number="20/189",
        language="en",
    )
    provider = FakeProvider()
    service = PriceService(database, provider)

    first = service.get_price(identity)
    second = service.get_price(identity)

    assert first.snapshot.cache_status == "live"
    assert second.snapshot.cache_status == "cache"
    assert provider.calls == 1
    assert second.quota.hourly_remaining == 99


def test_price_service_blocks_live_fetch_when_quota_is_exhausted(tmp_path):
    database = AppDatabase(tmp_path / "test.sqlite")
    identity = CardIdentity(
        canonical_id="swsh3-020",
        provider_ids={"pokewallet": "pk_sample"},
        name="Charizard VMAX",
        set_code="SWSH3",
        set_name="Darkness Ablaze",
        collector_number="20/189",
        language="en",
    )
    database.set_quota(
        QuotaState(
            provider="pokewallet",
            hourly_limit=100,
            hourly_remaining=0,
            daily_limit=1000,
            daily_remaining=900,
        )
    )
    provider = FakeProvider()

    try:
        PriceService(database, provider).get_price(identity)
    except ProviderError as exc:
        assert "quota" in str(exc).lower()
    else:
        raise AssertionError("Expected exhausted quota to block live fetch")

    assert provider.calls == 0


def test_pokewallet_provider_uses_search_result_for_sample_ids():
    calls = []

    class FakeResponse:
        headers = {
            "X-RateLimit-Limit-Hour": "100",
            "X-RateLimit-Remaining-Hour": "99",
            "X-RateLimit-Limit-Day": "1000",
            "X-RateLimit-Remaining-Day": "999",
        }

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            import json

            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout):
        calls.append(request)
        if request.full_url.startswith("https://api.pokewallet.io/search?"):
            return FakeResponse(
                {
                    "results": [
                        {
                            "id": "pk_real_charizard",
                            "card_info": {
                                "clean_name": "Charizard VMAX",
                                "set_code": "SWSH3",
                                "card_number": "20/189",
                            },
                            "tcgplayer": {
                                "prices": [
                                    {
                                        "market_price": 12.34,
                                        "low_price": 10,
                                        "mid_price": 12,
                                        "high_price": 15,
                                    }
                                ]
                            },
                        }
                    ]
                }
            )
        raise AssertionError(f"Unexpected URL: {request.full_url}")

    identity = CardIdentity(
        canonical_id="swsh3-020",
        provider_ids={"pokewallet": "pk_sample_charizard_vmax"},
        name="Charizard VMAX",
        set_code="SWSH3",
        set_name="Darkness Ablaze",
        collector_number="20/189",
        language="en",
    )

    with patch("codexocr.providers.urlopen", fake_urlopen):
        result = PokewalletProvider("pk_test_123").fetch_price(identity)

    assert calls[0].headers["X-api-key"] == "pk_test_123"
    assert calls[0].headers["User-agent"] == "CodexOCR/0.1 Python API Client"
    assert calls[0].full_url.startswith("https://api.pokewallet.io/search?")
    assert len(calls) == 1
    assert result.snapshot.market == 12.34
    assert result.quota.hourly_remaining == 99


def test_pokewallet_provider_falls_back_to_simpler_search_queries():
    calls = []

    class FakeResponse:
        headers = {}

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            import json

            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if "Charizard+VMAX+SWSH3+20" in request.full_url:
            return FakeResponse({"results": []})
        return FakeResponse(
            {
                "results": [
                    {
                        "id": "pk_real_charizard",
                        "card_info": {
                            "clean_name": "Charizard VMAX",
                            "set_code": "SWSH3",
                            "card_number": "20/189",
                        },
                        "tcgplayer": {"prices": [{"market_price": 18.25}]},
                    }
                ]
            }
        )

    identity = CardIdentity(
        canonical_id="swsh3-020",
        provider_ids={"pokewallet": "pk_sample_charizard_vmax"},
        name="Charizard VMAX",
        set_code="SWSH3",
        set_name="Darkness Ablaze",
        collector_number="20/189",
        language="en",
    )

    with patch("codexocr.providers.urlopen", fake_urlopen):
        result = PokewalletProvider("pk_test_123").fetch_price(identity)

    assert len(calls) == 2
    assert "Charizard+VMAX+SWSH3" in calls[1]
    assert result.snapshot.market == 18.25


def test_pokewallet_provider_uses_card_endpoint_for_real_ids():
    calls = []

    class FakeResponse:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            import json

            return json.dumps({"tcgplayer": {"prices": [{"market_price": 7.5}]}}).encode("utf-8")

    def fake_urlopen(request, timeout):
        calls.append(request)
        return FakeResponse()

    identity = CardIdentity(
        canonical_id="swsh3-020",
        provider_ids={"pokewallet": "pk_real_charizard"},
        name="Charizard VMAX",
        set_code="SWSH3",
        set_name="Darkness Ablaze",
        collector_number="20/189",
        language="en",
    )

    with patch("codexocr.providers.urlopen", fake_urlopen):
        result = PokewalletProvider("pk_test_123").fetch_price(identity)

    assert calls[0].full_url == "https://api.pokewallet.io/cards/pk_real_charizard"
    assert result.snapshot.market == 7.5


def test_pokewallet_http_errors_include_response_message():
    error = HTTPError(
        url="https://api.pokewallet.io/search",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=BytesIO(b'{"error":"Forbidden","message":"Invalid API key or access denied"}'),
    )

    provider_error = _provider_error_from_http("search", error)

    assert "HTTP 403" in str(provider_error)
    assert "Invalid API key" in str(provider_error)


def test_pokewallet_cloudflare_errors_include_detail():
    error = HTTPError(
        url="https://api.pokewallet.io/search",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=BytesIO(
            b'{"title":"Error 1010: Access denied","detail":"The site owner has blocked access based on your browser signature."}'
        ),
    )

    provider_error = _provider_error_from_http("search", error)

    assert "Error 1010" in str(provider_error)
    assert "browser signature" in str(provider_error)
