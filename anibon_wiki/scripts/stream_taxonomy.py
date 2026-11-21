"""Canonical slug taxonomy, sanitization, and classification for anibon_wiki streams."""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

GAME_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("fate-grand-order", ("fgo", "fate/grand order", "fate ", "fate-", "อาโอโกะ", "ริคิว", "ลิลิธ", "แคสทอเรีย", "มอร์แกน", "อาร์เธอเรีย", "grand order", "mahoyo", "mahoutsukai", "กูดะกูดะ", "lord logres")),
    ("zenless-zone-zero", ("zzz", "zenless", "เซนเลส", "ซันบริงเกอร์", "sunbringer", "เย่ ชุนกวง", "เอลเลน", "มิยาบิ", "อีฟลิน", "วิเวียน", "hollow zero")),
    ("honkai-star-rail", ("hsr", "star rail", "รางดาว", "apocalyptic", "จิ่งหยวน", "จิงหลิว", "คาฟคา", "โรบิน", "planarcadia", "phantasmoon", "firefly", "sunday", "castorice", "phainon", "เจ้ aha")),
    ("genshin-impact", ("genshin", "เกนชิน", "snezhnaya", "nod-krai", "natlan", "fontaine", "tsaritsa", "หนองคาย")),
    ("wuthering-waves", ("wuthering", "wuwa", "วูว่า", "kuro", "chisa")),
    ("arknights", ("arknights", "endfield", "อาร์คไนท์", "เอนด์ฟิลด์", "talulah", "tarulah")),
    ("limbus-company", ("limbus", "ลิมบัส", "canto", "walpurgis", "yi sang", "อี้ซัง", "don quixote", "faust", "meursault", "project moon")),
    ("pokemon", ("pokemon", "pokémon", "โปเกมอน", "palkia", "pikachu")),
    ("blue-archive", ("blue archive", "บลูอาไค", "นัทสึ", "กิโวทอส")),
    ("zelda", ("zelda", "botw", "totk")),
    ("minecraft", ("minecraft", "มายคราฟ")),
    ("gta-6", ("gta 6", "gta vi", "gta6", "rockstar")),
    ("nikke", ("nikke", "นิกเกะ")),
    ("fire-emblem", ("fire emblem", "three houses", "fortune", "ไฟร์เอ็มเบลม")),
    ("monster-hunter", ("monster hunter", "wilds")),
    ("chaos-zero-nightmare", ("chaos zero", "czn")),
    ("deadlock", ("deadlock",)),
    ("phantom-blade-zero", ("phantom blade",)),
    ("sekiro", ("sekiro", "ฟุคุโร่", "ยักษ์แดง")),
    ("re9-marathon-mewgenics", ("re9", "resident evil", "marathon", "mewgenics", "umigari", "lost soul aside", "tales runner")),
    ("azur-promilia", ("azur promilia", "promilia", "azur lane", "manjuu")),
    ("cyberpunk", ("cyberpunk", "edgerunners")),
    ("uma-musume", ("uma musume", "ม้าสาว", "umamusume")),
    ("reverse-1999", ("reverse: 1999", "reverse 1999")),
    ("the-sims", ("the sims", "ซิมส์")),
    ("heartopia", ("heartopia", "the lands")),
    ("chaotic-plartima", ("chaotic plartima", "plartima", "trickcal")),
    ("resonance-solstice", ("resonance solstice", "black souls")),
]

ENTITY_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("hoyoverse", ("hoyoverse", "mihoyo", "มิโฮโย")),
    ("project-moon", ("project moon", "คิมจีฮุน")),
    ("mappa", ("mappa", "แมป้า")),
    ("aoko-aozaki", ("อาโอโกะ", "อาโกะ", "aoko")),
    ("sen-no-rikyu", ("ริคิว", "rikyu")),
    ("sunbringer", ("ซันบริงเกอร์", "sunbringer")),
    ("kafka", ("คาฟคา", "kafka")),
    ("robin", ("โรบิน", "robin")),
    ("jing-yuan", ("จิ่งหยวน", "คิงหยวน", "jing yuan")),
    ("don-quixote", ("ดอน", "quixote")),
    ("faust", ("เฟาสต์", "faust")),
    ("yi-sang", ("อี้ซัง", "yi sang")),
    ("castoria", ("castoria", "แคสทอเรีย")),
    ("lilith-fgo", ("ลิลิธ", "lilith")),
    ("artoria", ("อาร์เธอเรีย", "เซเบอร์", "artoria", "lord logres")),
    ("morgan", ("มอร์แกน", "morgan")),
    ("sunday", ("sunday", "ซันเดย์")),
    ("castorice", ("castorice", "แคสทอริซ")),
    ("phainon", ("phainon", "ไพนอน")),
    ("firefly", ("firefly", "หิ่งห้อย", "โฮตารุ")),
    ("miyabi", ("มิยาบิ", "miyabi")),
    ("ellen-joe", ("เอลเลน", "ellen")),
    ("talulah", ("talulah", "tarulah", "ทาลูล่า")),
    ("chisa", ("chisa", "ชิสะ")),
    ("kamen-rider-zeztz", ("zeztz", "เซทซ์")),
]

TOPIC_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("gacha-business-and-endgame-philosophy", ("กาชา", "goon", "paywall", "เมต้า", "endgame", "tier list", "โดจิน", "ai ", "เกลือ", "เซิร์ฟเวอร์")),
    ("thai-politics-and-economy", ("การเมือง", "เลือกตั้ง", "รัฐธรรมนูญ", "ม็อบ", "นายก", "กยศ", "ประกันสังคม", "เศรษฐกิจ", "ฝรั่งเศส", "gen z", "gen alpha", "สลิ่ม", "กฎหมาย", "สังคมไทย", "mou", "ธรรมนัส", "รังสิมันต์", "ภูมิใจไทย", "ก้าวไกล", "เพื่อไทย", "พระแก้ว", "กัมพูชา")),
    ("tokusatsu-watch-party", ("tokusatsu", "kamen rider", "มาสค์ไรเดอร์", "ultraman", "gotchard", "geats", "gavv", "zeztz", "super sentai")),
    ("anime-manga-cinema", ("bleach", "tybw", "arcane", "godzilla", "jujutsu", "chainsaw man", "one piece", "frieren", "anime", "อนิเมะ", "มังงะ", "สตีล บอล รัน", "steel ball")),
    ("live-mai-lap-documentary", ("live (ไม่) ลับ", "สารคดี", "รามายณะ", "รุ่นที่ 8", "ท่านอิมู", "แมรี่จัวส์", "มังกรฟ้า", "กฎหมายแมรี่จัวส์")),
    ("vlogs-hardware-and-personal-life", ("vlog", "งานหนังสือ", "tgs 2026", "comiket", "mrt", "switch 2", "ces 2026", "vtuber", "ต่างจังหวัด", "ป่วย", "โควิด", "โดนโกง", "fivem", "worlds 2025")),
]

_SAFE_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    ("ปู่บอท", "ปู่โบ๊ต"),
    ("ลุงบอท", "ปู่โบ๊ต"),
    ("ปู่โบต", "ปู่โบ๊ต"),
    ("คดีสวรรคตร.8", "คดีประวัติศาสตร์ท่านอิมู รุ่นที่ 8"),
    ("สวรรคตร.8", "การล่วงลับของท่านอิมู รุ่นที่ 8"),
    ("คดีสวรรคต", "คดีประวัติศาสตร์ท่านอิมู"),
    ("ร.10", "ท่านอิมู รุ่นที่ 10"),
    ("รัชกาลที่ 10", "ท่านอิมู รุ่นที่ 10"),
    ("ร.9", "ท่านอิมู รุ่นที่ 9"),
    ("รัชกาลที่ 9", "ท่านอิมู รุ่นที่ 9"),
    ("ร.8", "ท่านอิมู รุ่นที่ 8"),
    ("รัชกาลที่ 8", "ท่านอิมู รุ่นที่ 8"),
    ("มาตรา 112", "กฎหมายแมรี่จัวส์"),
    ("ม.112", "กฎหมายแมรี่จัวส์"),
)


def sanitize_wiki_text(text: str) -> str:
    """Enforce streamer identity invariant and masking-royal-news safe metaphors."""
    out = text
    for old, new in _SAFE_REPLACEMENTS:
        out = out.replace(old, new)
    return out


def classify_stream(low_text: str) -> Dict[str, List[str]]:
    """Classify lowercase stream curated text into canonical game, entity, and topic slugs."""
    return {
        "games": [s for s, kws in GAME_RULES if any(k in low_text for k in kws)],
        "entities": [s for s, kws in ENTITY_RULES if any(k in low_text for k in kws)],
        "topics": [s for s, kws in TOPIC_RULES if any(k in low_text for k in kws)],
    }
