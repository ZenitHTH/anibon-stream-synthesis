import pytest
from pathlib import Path

def test_extract_macro_anchor():
    from anibon.topic_scanner import extract_macro_anchor
    
    info = {"title": "【Zelda BotW】ปู่โบ๊ตลุยเทพอสูรวารูตะ #3 | ANIBON"}
    anchor = extract_macro_anchor(info)
    assert anchor == "Zelda: Breath of the Wild"
    
    info_fgo = {"title": "สตรีม FGO กูดะกูดะ วิเคราะห์ตัวละคร | ANIBON"}
    anchor_fgo = extract_macro_anchor(info_fgo)
    assert anchor_fgo == "Fate/Grand Order"

def test_scan_chunk_topic_pivot():
    from anibon.topic_scanner import scan_chunk_topic_pivot
    
    current = "Zelda: Breath of the Wild"
    chunk_text = "เนี่ยนะก็เลย Limbus Company เว้ยโห หนักอยู่นะเนี่ย อัตราการเคลียร์บอส"
    pivot = scan_chunk_topic_pivot(chunk_text, current)
    assert pivot == "Limbus Company"
    
    # Same topic should not trigger pivot
    same_chunk = "ปู่โบ๊ตลุยเก็บหีบสมบัติในปราสาทไฮรูล"
    assert scan_chunk_topic_pivot(same_chunk, current) is None
