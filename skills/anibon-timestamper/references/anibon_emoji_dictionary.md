# Anibon Channel Emoji & LiveChat Mood Dictionary

This reference file lists all exclusive Anibon channel emotes, standard YouTube global emotes, their subculture meanings, pulse weights, and mood classifications for `anibon-timestamper` and `anibon-livechat-analysis`.

> **MACHINE SOURCE**: `analyze_555.py` reads the JSON mirror of this dictionary at
> `skills/anibon-timestamper/resources/emoji_dictionary.json`. Each emote carries a
> `laugh` flag — only `laugh: true` emotes count as laugh markers when detecting
> `MEME_PULSE`. Flat/AFK/confusion/political/welcome emotes are `laugh: false`.
> Keep the JSON in sync when adding/removing emotes in this doc.

---

## 1. Exclusive Anibon Channel Emotes

| Custom Emote | Primary Mood Verdict | Visual & Subculture Context | Weight | Masking Trigger |
| :--- | :--- | :--- | :--- | :--- |
| `:_CunnyBoat:` / `:_cunnyboat:` | **CUTE_CUNNY_PULSE** | Yellow face with glasses crying waterfall tears (`😭` + glasses). Anime cute & funny reaction ("อู้ววว 😭 / น่ารักจนร้องไห้"). | `2.0` | None |
| `:_MonkeyBoat:` | **CHAOTIC_MEME_PULSE** | Pu Boat in wild monkey crouch pose (ท่าลิง / ทรงลิง). Spammed when Boat goes full unhinged chaotic mode ("ปั่นหลุดโลก"). | `2.2` | None |
| `:_Nerd:` | **NERD_EXPLAIN_PULSE** | Pu Boat pushing up glasses with finger in air ("Ackchyually 🤓"). Used when Boat over-explains lore, history, or mechanics. | `1.8` | None |
| `:_shutup:` / `:_Shutup:` | **DANCE_HYPE_PULSE** | PSY "Shut Up & Dance" meme image. Spammed when chat wants to dance / music jam peak. | `2.0` | None |
| `:Grind:` / `:_Grind:` | **DOWNBAD_MEME_PULSE** | Pu Boat grinning mischievous/horny face. Used when Boat acts downbad / reacts to cute female characters ("หื่น"). | `2.0` | None |
| `:_Ripfish:` / `:_RipFish:` | **HORNY_REACTION_PULSE** | Upright standing fish meme ("ปลาตื่น"). Spammed when chat or Boat experiences horny excitement ("ปลาตื่น / ค*ยตื่น"). | `2.0` | None |
| `:_noname:` / `:_NoName:` | **AFK_BRB_PULSE** | Grey plush doll on Boat's bed. Spammed by chat when Boat steps AFK / off-screen / BRB (ไปห้องน้ำ / พักสายตา). | `1.5` | None |
| `:_What:` | **CONFUSION_PULSE** | Pu Boat squinting behind yellow mic in utter confusion ("ห๊ะ? / อะไรวะเนี่ย / งงดิ / WTF"). | `1.8` | None |
| `:_WOW:` | **SHOCK_HYPE_PULSE** | Pu Boat with wide eyes & open mouth ("Poggers" / ว้าว). Spammed during lucky gacha, clutches, or shock reveals. | `1.8` | None |
| `:_Ahh:` | **BLISS_EUPHORIA_PULSE** | Head thrown back with mouth open. Extreme satisfaction, bliss, ear-gasmic music, or random shitpost ("อ๊าาา / ฟินสุดๆ"). | `1.5` | None |
| `:_Meh:` | **FLAT_REACTION_PULSE** | Deadpan close-up face staring blankly. Used when Boat tells a bad joke / dad joke ("มุขแป๊ก / กริบ"). | `1.2` | None |
| `:_MoneyBoat:` | **DONATION_PULSE** | SuperChat flood / Wealthy viewer flex / Money donation celebration. | `2.5` | None |
| `:_Tahaan:` | **SENSITIVE_POLITICAL** | Pu Boat in military camo uniform (ชุดทหารลายพราง). Army, conscription & military political banter. | `2.0` | `masking-royal-news` |
| `:_KonDee:` | **SENSITIVE_POLITICAL** | Pu Boat in yellow shirt with proud "Good person" ("คนดี") smile. 2547 color-shirt moralizing satire. | `1.8` | `masking-royal-news` |
| `:_NeoSlim:` | **SENSITIVE_POLITICAL** | Split Half-Red / Half-Yellow shirt meme ("เสื้อสองสี แดง-เหลือง"). Political fusion satire. | `2.0` | `masking-royal-news` |
| `:_Slim:` | **POLITICAL_ROLEPLAY_MEME** | Pu Boat in full yellow polo shirt. Chat roleplays 2547 yellow-shirt royalist loving any historical/game king (e.g. King Eric Bloodaxe). | `2.0` | `masking-royal-news` |
| `:_BoatSOM:` | **POLITICAL_BANTER_PULSE** | Pu Boat holding giant orange (ส้ม). Cheering Future Forward / Move Forward party ("อนาคตใหม่ / ก้าวไกล / ด้อมส้ม"). | `2.0` | `masking-royal-news` |
| `:_Tea:` | **DRAMA_NEWS_PULSE** | Sipping tea meme / Chat reacting to news, drama, gossip, or tea spilling ("จิบชา / เสือก / เม้าท์ฉ่ำ"). | `1.8` | None |
| `:_Yed:` | **SPICY_BANTER_PULSE** | High-intensity spicy banter / vulgar slang joke / peak chat reaction. | `2.0` | None |

---

## 2. Standard YouTube Global Emotes in Anibon Chat

| YouTube Global Emote | Primary Mood Verdict | Anibon Chat Subculture Usage | Weight |
| :--- | :--- | :--- | :--- |
| `:hand-pink_waving:` | **GREETING_WELCOME_PULSE** | Stream intro / Greeting Pu Boat when stream opens (`สวัสดี / หวัดดีโบ๊ท`) | `1.0` |
| `:face-blue-smiling:` | **MEME_PULSE** | Standard laughter flood alongside `555` (`ขำ / ฮา`) | `1.5` |
| `:face-purple-crying:` | **CUTE_CUNNY_PULSE** | Non-member substitute for `:_cunnyboat:` (`😭` cute & funny reaction) | `1.5` |
| `:face-red-droppy-eye:` / `:face-red-droppy-eyes:` | **ANGRY_OUTRAGE_PULSE** | Chat angry/outraged when Boat reports infuriating news (`เดือด / โกรธ / หัวร้อน`) | `1.8` |
| `:face-blue-wide-eyes:` / `:face-purple-wide-eyes:` | **SHOCK_PULSE** | Wide-eyed shock or surprise reaction (`ตกใจ / อึ้ง`) | `1.5` |
| `:cat-orange-whistling:` | **INNOCENT_WHISTLE_PULSE** | Whistling cat / Acting innocent after trolling or mistake (`ผิวปาก / ทำเป็นไม่รู้ไม่ชี้`) | `1.2` |
| `:face-red-heart-shape:` | **WHOLESOME_LOVE_PULSE** | Heart shape / Love, wholesome, and chat appreciation (`ใจฟู / เลิฟ`) | `1.5` |

---

## 4. Thai Internet Subculture & Humor Archetypes

When translating chat/talk energy into timestamps, map these common Thai stream humor patterns to tone-aware action verbs:

### A. Typo & Laughter Shorthand
- **`555` / `555+` / `55555`**: Standard laughter ("ha-ha-ha"). Density determines `MEME_PULSE`.
- **`ถถถถ` (The `555` Keyboard Struggle)**: Typing `555` without switching language from Thai to EN (`5` shares the key with `ถ`). Represents frantic, uncontrollable laughter.

### B. Modern Thai Stream Slang Vocabulary (2024–2025)
- **`ทำถึง` (Tam Thueng)**: Nailed it to perfection / peak quality performance $\rightarrow$ Verb recipe: `ทำถึง!`, `อลังการ`, `จัดเต็ม`.
- **`จะ Crazy` (Ja Crazy)**: Overwhelmed by absurdity or unbelievable luck $\rightarrow$ Verb recipe: `ฮาจะCrazy`, `อึ้งยับ`.
- **`อ่อม` (Awm)**: Underwhelming performance, bad luck, or low energy $\rightarrow$ Verb recipe: `อ่อมยับ`, `เซ็ง`.
- **`ตึง` (Tueeng)**: High skill / sweaty play / intense fight $\rightarrow$ Verb recipe: `ลุยตึง`, `ตึงจัด`.
- **`ตุย` (Dtui)**: Character died / team wipe $\rightarrow$ Verb recipe: `ตุยยับ`, `โดนตบตาย`.
- **`สภาพ` (Sà-pâab)**: Mocking a messy fail or state $\rightarrow$ Verb recipe: `สภาพ!`, `ฮาสภาพ`.

### C. Humor Archetypes & Verb Mapping

| Humor Archetype | Thai Chat / Talk Pattern | Meaning & Psychology | Timestamp Verb Recipe |
| :--- | :--- | :--- | :--- |
| **Sarcastic Hyping (ปั่น / อวยมีม)** | Hyping low-tier/trash unit (e.g. Eric Bloodaxe = "Grand Berserker", "META") | Pure ironical celebration. Treat low-rarity as god-tier. | `ฮาแซว`, `ปั่น`, `อวยมีม`, `แซวความเก่ง` |
| **Playful Envy / Coping (อิจฉาแซว)** | Screaming "กด dislike ละ", "โดนน้ำมนต์", "เกลือ" when host or chat gets gacha SSR | Not real anger; slapstick community joy & celebration. | `ฮาแชท`, `แซวตู้`, `ลุ้นกาชา`, `แฮปปี้` |
| **Debate & Flexing (เถียงแชท / ยัดจอก)** | Host arguing with chat over Grailing (อัดจอก) or playing off-meta | Friendly streamer vs chat banter & flex. | `ฮาเถียงแชท`, `อัดจอก`, `โชว์ของ` |
| **Miracle Clutch (ปาฏิหาริย์รอดตาย)** | HP remaining = 15, survival against all odds | Extreme comedic relief & unexpected hype. | `ปาฏิหาริย์!`, `รอดตายเฉียบขาด`, `ลุ้นปั๊มชนะ` |
| **Political Metaphor (การเมืองมีม)** | `: _Slim:`, `: _Tahaan:`, `: _BoatSOM:`, One Piece politics talk | Political satire & community roleplay (subject to safety masking). | `ถก`, `วิเคราะห์`, `เม้าท์มอย` |

---

## 5. Python Integration Dictionary

```python
ANIBON_EMOTE_DICTIONARY = {
    ":_CunnyBoat:":  ("CUTE_CUNNY_PULSE", 2.0),
    ":_MonkeyBoat:": ("CHAOTIC_MEME_PULSE", 2.2),
    ":_Nerd:":       ("NERD_EXPLAIN_PULSE", 1.8),
    ":_shutup:":     ("DANCE_HYPE_PULSE", 2.0),
    ":Grind:":       ("DOWNBAD_MEME_PULSE", 2.0),
    ":_Ripfish:":    ("HORNY_REACTION_PULSE", 2.0),
    ":_noname:":     ("AFK_BRB_PULSE", 1.5),
    ":_What:":       ("CONFUSION_PULSE", 1.8),
    ":_WOW:":        ("SHOCK_HYPE_PULSE", 1.8),
    ":_Ahh:":        ("BLISS_EUPHORIA_PULSE", 1.5),
    ":_Meh:":        ("FLAT_REACTION_PULSE", 1.2),
    ":_MoneyBoat:":  ("DONATION_PULSE", 2.5),
    ":_Tahaan:":     ("SENSITIVE_POLITICAL", 2.0),
    ":_KonDee:":     ("SENSITIVE_POLITICAL", 1.8),
    ":_NeoSlim:":    ("SENSITIVE_POLITICAL", 2.0),
    ":_Slim:":       ("POLITICAL_ROLEPLAY_MEME", 2.0),
    ":_BoatSOM:":    ("POLITICAL_BANTER_PULSE", 2.0),
    ":_Tea:":        ("DRAMA_NEWS_PULSE", 1.8),
    ":_Yed:":        ("SPICY_BANTER_PULSE", 2.0),
    ":hand-pink_waving:":       ("GREETING_WELCOME_PULSE", 1.0),
    ":face-blue-smiling:":      ("MEME_PULSE", 1.5),
    ":face-purple-crying:":     ("CUTE_CUNNY_PULSE", 1.5),
    ":face-red-droppy-eyes:":   ("ANGRY_OUTRAGE_PULSE", 1.8),
    ":face-blue-wide-eyes:":    ("SHOCK_PULSE", 1.5),
    ":cat-orange-whistling:":   ("INNOCENT_WHISTLE_PULSE", 1.2),
    ":face-red-heart-shape:":   ("WHOLESOME_LOVE_PULSE", 1.5),
}
```

