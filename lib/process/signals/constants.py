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
    "Minecraft.md": [
        "minecraft", "มายคราฟ", "มายคราฟต์", "curseforge", "เคิร์สฟอร์จ", "modpack", "ม็อดแพ็ค",
        "java 26.3", "bedrock 26.52", "bedrock", "เบดร็อก", "neoforge", "นีโอฟอร์จ", "fabric", "แฟบริก",
        "ender dragon", "มังกรดิเอ็นด์", "wither", "วิทเธอร์", "warden", "วาร์เดน", "breeze", "บรีซ",
        "trial chambers", "deep dark", "ancient city", "ominous vault", "mace", "กระบองเมซ",
        "allay", "น้องอัลเลย์", "villager", "ชาวบ้าน", "pillager", "พิลเลเจอร์", "iron golem", "ไอรอนโกเล็ม",
        "netherite", "เนเธอไรต์", "smithing template", "สมิทธิงเทมเพลต", "armor trim", "redstone", "เรดสโตน",
        "create mod", "jei", "sodium", "โซเดียม", "iris shaders", "rlcraft", "dawncraft",
    ],
    "Minecraft_Cisco.md": [
        "minecraft", "มายคราฟ", "มายคราฟต์", "cisco", "cisco's", "dragonfyre", "ซิสโก้",
        "reforging table", "salvaging table", "reforge", "รีฟอร์จ",
        "archmage spellbook", "gift of origin", "shadow gift", "shadow grave", "perfect silence",
        "ice breaker", "earth quake", "endless quiver", "forge gem", "เจมอัปเกรด",
        "lomar", "โลมาร์", "pillager", "พิลเลเจอร์", "allay", "อัลเลย์",
        "fire dragon", "ice dragon", "smithing template", "สมิทธิงเทมเพลต",
        "nether portal", "auto trader", "breeder trader", "iron golem", "ไอรอนโกเล็ม",
    ],
    "Chaos_Zero_Nightmare.md": [
        "chaos zero nightmare", "chaos zero", "czn", "คาเซน่า", "คาเซนา",
        "เคอส", "เคออส", "เคออส ซีโร่ ไนท์แมร์", "ฝันร้าย",
        "epiphany", "trauma code", "ทรอม่าโค้ด", "omega code", "โอเมก้าโค้ด",
        "memory fragment", "เมมโมรี่แฟรกเมนต์", "พเนอร์", "พาร์ทเนอร์", "ผู้ชี้ทาง", "navigator",
        "galactic disaster", "มหันตภัยกาแล็กซี",
        "rossweisse", "รอสไวส์", "รอซึวสึ", "sereniel", "เซรนิว", "เซรณี", "เซเรเนียล",
        "nebia", "เนเบีย", "เนบีย", "renoir", "เรนัวร์", "เลนัว",
    ],
    "Wuthering_Waves.md": [
        "wuthering waves", "wuthering", "wuwa", "เวฟ", "rover", "jinhsi", "จินซี", "changli", "ฉางลี่", "yinlin", "อินหลิน",
        "jiyan", "จี้หยาน", "shorekeeper", "ชอร์คีปเปอร์", "camellya", "คาเมลเลีย", "xiangli yao", "เซียงลี่เหยา",
        "cantarella", "คันตาเรลล่า", "suoming", "ซั่วหมิง", "hsin", "ซิน", "qingxiao", "jingran",
        "echo", "tacet field", "sonance sphere",
    ],
    "Zenless_Zone_Zero.md": [
        "zenless zone zero", "zenless", "zzz", "new eridu", "bangboo",
        "hollow zero", "proxies", "proxy", "inter-knot",
        "phoenix", "ฟีนิกซ์", "severian", "เซเวเรียน", "sunbringer", "ซันบริงเกอร์", "springer", "สปริงเกอร์", "สปริเกอร์", "krampus", "roscaelifer", "eldreda", "lindverne", "dracaene",
        "miyabi", "มิยาบิ", "yanagi", "ยานางิ", "caesar", "ซีซาร์", "burnice", "เบอร์นิซ", "jane doe", "เจนโด",
    ],
    "Blue_Archive.md": [
        "blue archive", "kivotos", "schale", "sensei", "halo festival", "total assault",
        "kisaki", "คิซากิ", "hoshino", "โฮชิโนะ", "shiroko", "ชิโรโกะ", "hina", "ฮินะ", "mika", "มิกะ", "kuroko", "คุโรโกะ", "rio", "ริโอ", "seia", "เซยะ",
        "tsumugi", "สึมุกิ",
    ],
    "Honkai_Star_Rail.md": [
        "honkai star rail", "star rail", "hsr", "astral express", "trailblazer",
        "stellaron", "simulated universe", "divergent universe", "จักรวาลจำลอง",
        "penacony", "เพนาโคนี่", "acheron", "อาเครอน", "aventurine", "อะเวนทูรีน",
        "firefly", "ไฟร์ฟลาย", "feixiao", "เฟยเซียว", "sparxie", "สปาร์กซี่", "sparkle", "สปาร์กเคิล",
        "yao guang", "เหยาจวง", "ปิติสุข", "elation", "memory of chaos", "moc",
        "pearl", "เพิร์ล", "ไข่มุก", "nihilux", "นิฮิรัก", "aha", "อาฮา",
        "sunday", "ซันเดย์", "fugue", "ฟูจิ", "robin", "โรบิน", "boothill", "บูทฮิลล์",
        "yunli", "หยุนหลี่", "jiaoqiu", "เจียวชิว", "lingsha", "ลิงชา", "the herta", "aglaea", "castorice", "tribbie",
        "rappa", "แรปป้า", "planarcadia", "พลานาร์เคเดีย", "amphoreus", "แอมฟอรัส", "evernight", "cyrene", "phainon",
    ],
    "Genshin_Impact.md": [
        "genshin impact", "genshin", "teyvat", "archon", "primogem",
        "spiral abyss", "paimon", "barbatos", "บาร์บาทอส", "morax", "โมแรกซ์",
        "raiden shogun", "ไรเดน", "nahida", "นาฮิดา", "furina", "ฟูรินา", "mavuika", "มาวิกา",
        "natlan", "เนตลัน", "fontaine", "ฟอนเทน", "sumeru", "สุเมรุ", "inazuma", "อินาซึมะ",
        "liyue", "หลีเยว่", "mondstadt", "มอนด์สตัดท์", "fatui", "ฟาตุย", "harbinger",
        "nod-krai", "น็อด-ไกร", "snezhnaya", "สเนซนายา", "tsaritsa", "ดองทรัพยากร",
        "mitya", "มิตยา", "valeriy", "วาเลริย์",
        "chasca", "ชาสก้า", "xilonen", "ชิโลเนน", "kinich", "คินิช", "mualani", "มัวลานี่",
        "citlali", "ซิทลาลี", "ororon", "โอโรลอน", "kachina", "คาชิน่า", "mizuki", "มิสึกิ", "varesa", "วาเรซ่า",
        "neuvillette", "นิววิลเล็ต", "arlecchino", "อาร์เลคคิโน", "navia", "นาเวีย",
    ],
    "references/stream/fgo-knowledge.md": [
        "fate grand order", "fgo", "chaldea", "servant", "noble phantasm", "saint quartz",
        "grand servant", "grand score", "grand substitute", "tamamo", "ทามาโมะ", "ciel",
    ],
    "Deadlock.md": [
        "deadlock", "patron", "trooper", "mid boss", "flex slot", "spirit power",
        "abrams", "เอแบรห์มส์", "bebop", "บีบ็อป", "dynamo", "ไดนาโม", "grey talon", "เกรย์ ทาลอน",
        "haze", "เฮซ", "infernus", "อินเฟอร์นัส", "ivy", "ไอวี่", "kelvin", "เคลวิน",
        "lady geist", "เลดี้ ไกส์ต", "lash", "แลช", "mcginnis", "แม็กกินนิส", "mirage", "มิราจ",
        "mo & krill", "โม แอนด์ คริลล์", "paradox", "พาราด็อกซ์", "pocket", "พ็อกเก็ต",
        "seven", "เซเว่น", "shiv", "ชิฟ", "vindicta", "วินดิกต้า", "viscous", "วิสคัส",
        "warden", "วอร์เดน", "wraith", "เรธ", "yamato", "ยามาโตะ",
        "violet", "nurse harrow",
        "เดดล็อก", "เดดล็อค", "baba yaga", "yamato", "abrams", "shiv", "infernus",
    ],
    "Sekiro_Shadows_Die_Twice.md": [
        "sekiro", "shadows die twice", "kusabimaru", "posture", "shinobi", "dragonrot",
    ],
    "Eternal_Return.md": [
        "eternal return", "lumia island", "seres", "เซเรส",
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
        "wis'adel", "วิชอาเดล", "logos", "โลโกส", "theresa", "เทเรซ่า", "shu", "สุ", "degenbrecher", "pepe",
        "closure", "โคลเชอร์", "esperanta", "เอสเปรันต้า",
    ],
    "Arknights_Endfield.md": [
        "endfield", "arknights endfield", "เอนด์ฟิลด์", "talos-ii", "si", "ซี", "typhoeus", "ไทฟอน",
    ],
    "Honkai_Impact_3_Part2.md": [
        "honkai impact 3rd", "honkai impact", "hi3", "สามเค", "ฮงไก", "herrscher of time", "senadina", "เซนาดิน่า",
    ],
    "Bleach.md": [
        "bleach", "บลีช", "เทพมรณะ", "bankai", "บังไค", "zanpakuto", "ดาบฟันวิญญาณ",
        "shikai", "ชิไค", "ichigo", "อิจิโกะ", "soul society", "โซลโซไซตี้",
        "quincy", "ควินซี่", "espada", "เอสปาด้า", "hollow", "ฮอลโลว์", "ยมทูต",
    ],
    "Zelda_Breath_of_the_Wild.md": [
        "zelda", "breath of the wild", "botw", "tears of the kingdom", "totk", "เซลด้า",
        "link", "ไฮรูล", "hyrule", "sheikah", "ชีคาห์", "korok", "โคโรค", "calamity ganon",
    ],
    "Dinoblade.md": [
        "dinoblade", "ไดโนเบลด", "ไดโนเสาร์คาบดาบ", "t-rex",
    ],
    "Heartopia.md": [
        "heartopia", "ฮาร์โทเปีย", "ฮาร์ทโทเปีย",
    ],
    "Tokusatsu_Project_RED.md": [
        "project red", "project r.e.d.", "โปรเจกต์เรด", "supersentai", "ซุปเปอร์เซนไต",
        "kamen rider", "มาสค์ไรเดอร์", "คาเมนไรเดอร์", "ultraman", "อุลตร้าแมน",
        "gavv", "กาฟ", "geats", "กีทส์", "gotchard", "ก็อตชาร์ด", "boonboomger", "บูนบูมเจอร์",
    ],
    "Limbus_Company.md": [
        "limbus company", "limbus", "dante", "golden bough", "mephistopheles", "sinners", "canto",
        "ลิมบัส", "แดนเต้", "vergilius", "เวอร์จิล", "เมฟิสโตเฟเลส", "อีโก้", "ego", "corrosion",
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
