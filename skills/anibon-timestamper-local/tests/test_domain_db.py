import pytest
from pathlib import Path

def test_query_ygo_by_archetype():
    from anibon.domain_db import query_ygo_by_archetype
    cards = query_ygo_by_archetype("Raidraptor", limit=5)
    assert len(cards) > 0
    assert all("Raidraptor" in c for c in cards)

def test_query_fgo_servants():
    from anibon.domain_db import query_fgo_servants
    servants = query_fgo_servants(["Oberon", "Morgan"])
    assert len(servants) > 0
    names = [s["name"] for s in servants]
    assert "Oberon" in names or "Morgan" in names
    for s in servants:
        assert "className" in s

def test_query_pokemon():
    from anibon.domain_db import query_pokemon
    p = query_pokemon("Garchomp")
    assert p is not None
    assert p["name_en"] == "Garchomp"
    assert "กาเบรียส" in p["name_th_official"]

def test_resolve_entities_for_chunk():
    from anibon.domain_db import resolve_entities_for_chunk
    chunk_text = "ปู่โบ๊ตวิเคราะห์เด็ค เรดแรปเตอร์ เจอขัดด้วย แม็กซ์ ซี แต่ยังกาง อัลทิเมตฟอลคอน ได้"
    entities = resolve_entities_for_chunk(chunk_text, max_entities=12)
    assert len(entities) > 0
    assert any("Raidraptor" in e for e in entities)
    assert len(entities) <= 12
