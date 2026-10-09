import pytest
from pathlib import Path

def test_load_and_match_phonemes():
    from anibon.phonetic_bridge import load_phonetic_bridge, match_phonemes
    
    bridge = load_phonetic_bridge()
    assert isinstance(bridge, dict)
    assert len(bridge) > 0
    assert "เรดแรปเตอร์" in bridge
    assert bridge["เรดแรปเตอร์"]["en"] == "Raidraptor"
    assert bridge["เรดแรปเตอร์"]["domain"] == "yugioh"
    
    text = "ปู่โบ๊ตวิเคราะห์เด็ค เรดแรปเตอร์ เจอขัดด้วย แม็กซ์ ซี แต่ยังกาง อัลทิเมตฟอลคอน ได้"
    hits = match_phonemes(text, bridge)
    assert len(hits) >= 3
    en_names = [h["en"] for h in hits]
    assert "Raidraptor" in en_names
    assert "Maxx \"C\"" in en_names
    assert "Raidraptor - Ultimate Falcon" in en_names

def test_match_phonemes_pokemon_and_limbus():
    from anibon.phonetic_bridge import load_phonetic_bridge, match_phonemes
    
    bridge = load_phonetic_bridge()
    text = "ส่งตัว การ์โชมป์ และ เป็ดต้นหอม ลงสู้ ก่อนที่วันพรุ่งนี้ ริมัส คันเ 10 จะมา"
    hits = match_phonemes(text, bridge)
    en_names = [h["en"] for h in hits]
    assert "Garchomp" in en_names
    assert "Farfetch'd" in en_names
    assert "Limbus Company" in en_names
    assert "Canto X" in en_names
