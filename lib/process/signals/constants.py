#!/usr/bin/env python3
"""Signal detection constants, keywords, regexes, and domain templates.

Acts as the header definition file for signal_detector.py.
"""
from __future__ import annotations

import re

# ── Stage 1 Game-Exclusive Special Words ──────────────────────────────────
# Exclusive franchise titles, unique world/system/currency mechanics, and signature terms.
# Common Japanese/Western character given names are excluded to prevent cross-game collisions.

GAME_SPECIAL_WORDS: dict[str, list[str]] = {
    "Chaos_Zero_Nightmare.md": [
        "chaos zero nightmare", "chaos zero", "czn", "คาเซน่า", "คาเซนา",
        "เคอส", "เคออส", "ฝันร้าย",
        "epiphany", "trauma code", "ทรอม่าโค้ด", "omega code", "โอเมก้าโค้ด",
        "memory fragment", "เมมโมรี่แฟรกเมนต์", "พเนอร์", "พาร์ทเนอร์",
        "rossweisse", "รอสไวส์", "รอซึวสึ", "sereniel", "เซรนิว", "เซรณี", "เซเรเนียล",
        "nebia", "เนเบีย", "เนบีย", "renoir", "เรนัวร์", "เลนัว",
    ],
    "Wuthering_Waves.md": [
        "wuthering waves", "wuthering", "wuwa", "เวฟ", "rover", "jinhsi", "changli", "yinlin",
        "echo", "tacet field", "sonance sphere",
    ],
    "Zenless_Zone_Zero.md": [
        "zenless zone zero", "zenless", "zzz", "new eridu", "bangboo",
        "hollow zero", "proxies", "proxy", "inter-knot",
    ],
    "Blue_Archive.md": [
        "blue archive", "kivotos", "schale", "sensei", "halo festival", "total assault",
    ],
    "Honkai_Star_Rail.md": [
        "honkai star rail", "star rail", "hsr", "astral express", "trailblazer",
        "stellaron", "simulated universe",
    ],
    "Genshin_Impact.md": [
        "genshin impact", "genshin", "teyvat", "archon", "primogem",
        "spiral abyss", "paimon",
    ],
    "references/stream/fgo-knowledge.md": [
        "fate grand order", "fgo", "chaldea", "servant", "noble phantasm", "saint quartz",
    ],
    "Deadlock.md": [
        "deadlock", "patron", "trooper", "mid boss", "flex slot", "spirit power",
    ],
    "Sekiro_Shadows_Die_Twice.md": [
        "sekiro", "shadows die twice", "kusabimaru", "posture", "shinobi", "dragonrot",
    ],
    "Eternal_Return.md": [
        "eternal return", "lumia island",
    ],
    "../anibon-world-identity/references/Yu-Gi-Oh DATA/ygo_cards.db": [
        "yu-gi-oh", "yugioh", "master duel", "duel monsters",
    ],
    "Pokemon_PvP.md": [
        "pokemon", "โปเกมอน", "pikachu", "pokedex", "pvp",
    ],
    "Pokemon_Radical_Red.md": [
        "radical red", "pokemon radical red",
    ],
    "Arknights.md": [
        "arknights", "rhodes island", "oripathy", "originium", "doctor", "amiya", "อาร์คไนท์", "โรดส์",
    ],
    "Limbus_Company.md": [
        "limbus company", "limbus", "dante", "golden bough", "mephistopheles", "sinners", "canto", "ลิมบัส", "แดนเต้",
    ],
}

# ── Stage 1 Blocked Words & Character Name Blacklist ──────────────────────
# Common Japanese and Western given names that cross multiple games/anime.
# Blocked from Stage 1 game voting; resolved in Stage 2 entity scoping only.

COMMON_CHARACTER_NAMES_BLACKLIST: set[str] = {
    # Japanese common given names / popular gacha shared names
    "yuki", "ยูกิ", "rin", "ริน", "mika", "มิกะ", "hoshino", "โฮชิโนะ", "shiroko", "ชิโรโกะ",
    "arona", "อาโรน่า", "lucy", "ลูซี่", "alice", "อลิส", "yvonne", "อีวอน", "อีวอนน์",
    "kuro", "คุโระ", "emma", "เอ็มม่า", "chizuru", "ชิซุรุ", "miyabi", "มิยาบิ",
    "yanagi", "ยานางิ", "dante", "แดนเต้", "faust", "เฟาสต์", "morgan", "มอร์แกน",
    "arthur", "อาร์เธอร์", "nero", "เนโร", "jeanne", "ฌาน", "sakura", "ซากุระ",
    "ren", "เรน", "haru", "ฮารุ", "aoi", "อาโออิ", "sora", "โซระ", "hikari", "ฮิคาริ",
    "tsubasa", "ซึบาสะ", "kaito", "ไคโตะ", "shiki", "ชิกิ", "shirou", "ชิโร่",
    "shin", "ชิน", "kai", "ไค", "jin", "จิน", "rei", "เรย์", "maya", "มายะ",
    "sara", "ซาร่า", "elena", "เอเลน่า", "maria", "มาเรีย", "clara", "คลาร่า",
    "diana", "ไดอาน่า",
}

AMBIGUOUS_SINGLE_TOKENS: set[str] = {
    "blue", "thai", "japan", "dark", "super", "grand", "star", "night", "zero",
    "shadow", "shadows", "impact", "zone", "order", "return", "hunter", "wilds",
    "fair", "convention", "book", "stream", "online", "project", "chronicle",
}

GENERIC_GAMING_STANDING_WORDS: set[str] = {
    "บอส", "กาชา", "เกลือ", "หลุดเรท", "โรล", "ตู้", "การันตี", "เพชร", "เหรียญ",
    "ดาเมจ", "คริ", "atk", "def", "hp", "sp", "mp", "บัฟ", "ดีบัฟ", "สเตตัส",
    "คอมโบ", "สตรีค", "แพตช์", "อัปเดต", "เนิร์ฟ", "เนิฟ", "บั๊ก", "แล็ก", "ปิง",
    "solo", "parry", "dodge", "dash", "ultimate", "ult", "สกิล", "ท่าไม้ตาย",
    "gacha", "boss", "damage", "crit", "buff", "debuff", "nerf", "patch", "roll",
}

STAGE1_BLOCKED_EXTRA: set[str] = {
    "fate", "เฟท", "servant", "nexon", "เน็กซอน",
}

SPECIFIC_KINDS: set[str] = {
    "game", "tokusatsu", "anime", "event", "publisher", "bookstore", "vlog_theme",
}

DUPE_TIER_RE = re.compile(
    r"\b(?:[CEce][0-6]|[Ss][0-6]|[Rr][1-5]|[Mm][0-6])\b|"
    r"(?:ระดับ|ขั้น|ดาว|ก๊อปปี้|ปลด)\s*[0-6]"
)

# ── ASR & Audio Noise Regular Expressions ─────────────────────────────────

NOISE_BRACKET_RE = re.compile(
    r"\[(?:เพลง|ดนตรี|เสียงดนตรี|เสียงปรบมือ|เสียงหัวเราะ|หัวเราะ|เสียงเอฟเฟกต์|Music|Applause|Laughter|Cheering)\]|"
    r"\((?:เพลง|ดนตรี|เสียงดนตรี|เสียงปรบมือ|เสียงหัวเราะ|หัวเราะ|เสียงเอฟเฟกต์|Music|Applause|Laughter|Cheering)\)",
    flags=re.IGNORECASE,
)
SPEAKER_MARKER_RE = re.compile(r"(?:^|\s)(?:>>+|>>>+)\s*")
MUSIC_NOTES_RE = re.compile(r"[♪♫♬♩]+")
MULTI_SPACE_RE = re.compile(r"\s+")
EXTENDED_CHAR_REPEAT_RE = re.compile(r"(.)\1{7,}")

# Private backward-compatibility aliases
_NOISE_BRACKET_RE = NOISE_BRACKET_RE
_SPEAKER_MARKER_RE = SPEAKER_MARKER_RE
_MUSIC_NOTES_RE = MUSIC_NOTES_RE
_MULTI_SPACE_RE = MULTI_SPACE_RE
_EXTENDED_CHAR_REPEAT_RE = EXTENDED_CHAR_REPEAT_RE

# ── Domain Guidance Keywords and Instruction Blocks ───────────────────────

SPECIFIC_TOKU_KEYWORDS: set[str] = {
    "คาเมนไรเดอร์", "มาสค์ไรเดอร์", "คาเมน ไรเดอร์", "เซนไต", "ซุปเปอร์เซนไต",
    "อุลตร้าแมน", "gavv", "geats", "gotchard", "boonboomger", "king-ohger",
    "เฮนชิน", "เข็มขัดแปลงร่าง", "เข็มขัดไรเดอร์", "แปลงร่าง", "โทคุซัตสึ", "โทคุสะสึ", "ไคจู",
}

GAMING_MATCH_MARKERS: set[str] = {
    "gacha", "boss", "limbus", "genshin", "arknights", "กาชา",
}

TOKUSATSU_TAGS: list[str] = [
    "[WatchParty]", "[Reaction]", "[Lore]", "[Review]", "[Tierlist]",
]
TOKUSATSU_INSTRUCTION_BLOCK: str = """\
## DETECTED DOMAIN: TOKUSATSU (มาสค์ไรเดอร์ / ขบวนการเซนไต / อุลตร้าแมน)
- Format: Watch Party or Franchise Lore Discussion.
- Key Terms & Characters:
  * Kamen Rider Gavv (ไรเดอร์กาฟ), Gotchard (ก็อตชาร์ด), Geats (กีทส์), Boonboomger (บูนบูมเจอร์)
  * Henshin (เฮนชิน/แปลงร่าง), Rider Belt (เข็มขัดแปลงร่าง), Final Form (ร่างพัฒนา/ร่างสุดยอด), DX Toys
- Focus: Highlight streamer's intense reactions, shock, or laugh at on-screen fight/transformation scenes.
- FIRST-VERBS: กรี๊ดลั่น!, เหวอ!, อึ้งฟอร์มใหม่, ชำแหละเนื้อเรื่อง, จัดอันดับสูท, บ่นราคาของเล่น, ปั่น
"""

GAMING_TAGS: list[str] = [
    "[Gameplay]", "[Gacha]", "[Boss]", "[Story]", "[Tierlist]",
]
GAMING_INSTRUCTION_BLOCK: str = """\
## DETECTED DOMAIN: GAMING & GACHA
- Format: Gameplay, Gacha pull, or Game Lore discussion.
- Focus: Distinguish between gacha summons, tough boss encounters, and story dialogue.
- FIRST-VERBS: เปิดกาชา, ลุ้นตัวทอง, สู้บอส, ผ่านด่าน, หัวร้อน!, ช็อกกาชาเกลือ, เจาะลึกสตอรี่
"""

ANIME_TAGS: list[str] = [
    "[WatchParty]", "[Reaction]", "[Review]", "[Talk]",
]
ANIME_INSTRUCTION_BLOCK: str = """\
## DETECTED DOMAIN: ANIME & MANGA
- Format: Anime discussion, review, or seasonal watch party.
- FIRST-VERBS: ป้ายยา, สับเละ, อวยยับ, วิเคราะห์อนิเมชั่น, ชวนคุยตอนล่าสุด
"""

TALK_TAGS: list[str] = [
    "[News]", "[Talk]", "[Chat]",
]
TALK_INSTRUCTION_BLOCK: str = """\
## DETECTED DOMAIN: POLITICS, SOCIETY & NEWS
- Format: Political critique, social news, or legal/agency commentary.
- FIRST-VERBS: ชำแหละ, จวกยับ, สับเละ, บ่นอุบ, โวยวาย, วิเคราะห์, กางตัวเลข, เตือน
"""
