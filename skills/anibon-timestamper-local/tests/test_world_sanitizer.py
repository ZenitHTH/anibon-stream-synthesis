import pytest
from pathlib import Path

def test_sanitize_pokemon_names_and_stutter():
    from anibon.world_sanitizer import sanitize_pokemon_names, clean_token_stutters
    
    raw = "01:15:00 - [Gameplay] ใช้ การ์โชมป์ สู้ใน Zelda: Breath of the Wildild"
    step1 = sanitize_pokemon_names(raw)
    assert "การ์โชมป์ (Garchomp)" in step1
    
    step2 = clean_token_stutters(step1)
    assert "Wildild" not in step2
    assert "Wild" in step2

def test_ensure_outro_timestamp():
    from anibon.world_sanitizer import ensure_outro_timestamp
    
    existing = "07:00:00 - [Gameplay] สำรวจโซนภูเขาไฟ\n"
    last_chunk = "(07:23:15) ขอบคุณทุกคนมากครับ ราตรีสวัสดิ์เจอกันใหม่ไลฟ์หน้า บ๊ายบายครับ"
    
    updated = ensure_outro_timestamp(existing, last_chunk)
    assert "07:23:15 - [Ending]" in updated
    assert "ขอบคุณทุกคน" in updated

def test_ensure_outro_not_duplicated():
    from anibon.world_sanitizer import ensure_outro_timestamp
    
    existing = "07:23:15 - [Ending] ปู่โบ๊ตกล่าวขอบคุณผู้ชมและปิดสตรีม\n"
    last_chunk = "(07:23:15) ขอบคุณทุกคนมากครับ ราตรีสวัสดิ์"
    
    # Should not duplicate if [Ending] stamp is already present in last minutes
    updated = ensure_outro_timestamp(existing, last_chunk)
    assert updated.count("[Ending]") == 1
