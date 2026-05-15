from codexocr.catalog import identity_from_pokemon_tcg_card, sync_pokemon_tcg_catalog
from codexocr.database import AppDatabase


class FakeCatalogClient:
    def iter_cards(self, query=None, max_pages=1):
        yield {
            "id": "sv1-198",
            "name": "Miriam",
            "number": "198",
            "set": {"id": "sv1", "name": "Scarlet & Violet", "printedTotal": 198},
            "images": {"large": "https://example.test/miriam.png"},
        }


def test_identity_from_pokemon_tcg_card_maps_core_fields():
    identity = identity_from_pokemon_tcg_card(
        {
            "id": "base1-4",
            "name": "Charizard",
            "number": "4",
            "set": {"id": "base1", "name": "Base Set", "printedTotal": 102},
            "images": {"small": "https://example.test/charizard.png"},
        }
    )

    assert identity.canonical_id == "base1-4"
    assert identity.set_code == "BASE1"
    assert identity.collector_number == "4/102"


def test_sync_pokemon_tcg_catalog_upserts_cards(tmp_path):
    database = AppDatabase(tmp_path / "test.sqlite")
    summary = sync_pokemon_tcg_catalog(database, client=FakeCatalogClient())

    assert summary.imported == 1
    assert database.get_card("sv1-198").name == "Miriam"
