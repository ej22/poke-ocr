from codexocr.database import AppDatabase
from codexocr.models import CardIdentity, PriceSnapshot, QuotaState
from codexocr.providers import PriceService, PricingResult


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
