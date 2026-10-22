# Chaining Weight Signal Detector & Per-Game Special-Word Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `signal_detector.py`, `prompts.py`, and `knowledge_reader.py` to strip universal gaming standing words (`E0–E6`, `C0–C6`, `S1–S6`, `กาชา`, `บอส`, `เกลือ`) AND common cross-game character names (`Yuki / ยูกิ`, `Rin / ริน`, `Mika / มิกะ`, `Hoshino`, `Shiroko`, `Lucy`, `Alice`, `Yvonne`, `Kuro`, `Emma`, `Miyabi`, `Chizuru`), score Stage-1 game detection strictly on **Game-Exclusive Special Words** (Franchise Titles + Unique Mechanics/Currencies/World Terms), propagate weights across chunks via temporal chaining ($W_t(g) = \alpha \cdot W_{t-1}(g) + S_t^{\text{special}}(g)$), and unlock character names only in Stage 2 for the winning game.

**Architecture:**
1. **Two-Stage Separation (Game Identification vs. Character Resolution):**
   - **Stage 1 — Game Identification (`signal_detector.py`):** Uses ONLY **Franchise Titles** and **Exclusive World/System/Currency Mechanics** (`GAME_SPECIAL_WORDS`). Common Japanese/Western given names (`COMMON_CHARACTER_NAMES_BLACKLIST`, e.g. `yuki`, `ยูกิ`, `rin`, `mika`, `hoshino`, `shiroko`, `arona`, `lucy`, `alice`, `yvonne`, `kuro`, `emma`, `chizuru`, `miyabi`, `yanagi`, `dante`, `faust`, `morgan`, `oberon`) and normal gaming standing words (`GENERIC_GAMING_STANDING_WORDS` + `DUPE_TIER_RE`) are **blocked** from Stage-1 game voting—including overriding legacy entries in `knowledge.json` (`'ยูกิ'`, `'hoshino'`, `'shiroko'`, `'arona'`).
   - **Stage 2 — Scoped Character Resolution (`knowledge_reader.py` + `prompts.py`):** Once Stage 1's chained weight $W_t(g)$ identifies the active game(s), `build_chunk_entity_context()` unlocks the character table (`Yuki`, `Rin`, `Mika`, `Chizuru`, `Diana`, `Maribell`, `Rossweisse`) **only** from the winning game's markdown file (`allowed_sources`), preventing cross-game character collisions.
2. **Temporal Chaining Weight (`detect_signals_for_chunks`):** Seeds $W_0(g)$ from stream metadata (`info.json`), chains $W_t(g) = 0.88 \cdot W_{t-1}(g) + S_t^{\text{special}}(g)$, and outputs normalized `candidates` with matched special words per chunk.
3. **Context + Weight Prompt Guard (`prompts.py`):** Injects `CANDIDATE DOMAIN WEIGHTS` + matched special words + standing-word/common-name guard into the prompt.

**Tech Stack:** Python 3.10+, `unittest` / `pytest`, JSON, Markdown.

**Spec:** Conversation context (`jduUyRfQwss` CZN 1st Anniversary stream analysis).

---

## Stage-1 Per-Game Special Words Specification (Zero Common Character Given Names)

Stage-1 `GAME_SPECIAL_WORDS` contains **only** franchise titles, unique currencies, unique world/faction names, unique combat systems, and unmistakable multi-syllable signature terms. Common Japanese/Western given names (`Yuki`, `Rin`, `Mika`, `Hina`, `Yuuka`, `Hoshino`, `Shiroko`, `Kuro`, `Emma`, `Lucy`, `Alice`, `Yvonne`, `Chizuru`, `Miyabi`, `Yanagi`, `Phoebe`, `Carlotta`, `Faust`, `Dante`, `Morgan`) are **excluded** from Stage 1 and resolved in Stage 2 via `entity_glossary.json`:

| Knowledge File | Stage-1 Exclusive Special Words (Franchise Titles / World / Currencies / Unique Systems Only) |
| :--- | :--- |
| **`Chaos_Zero_Nightmare.md`** | `chaos zero nightmare`, `czn`, `เคออส ซีโร่ ไนท์แมร์`, `เคออสซีโร่`, `คาเซน่า`, `คาเซนา`, `เคอส`, `เคออส`, `ฝันร้าย`, `เคซะได้แม่`, `แo nightman`, `แค zero ไแม`, `epiphany`, `อิพิฟานี`, `ego manifestation`, `trauma code`, `ทราวม่าโค้ด`, `omega code`, `โอเมก้าโค้ด`, `memory fragment`, `เมมโมรี่แฟรกเมนต์`, `galactic disaster`, `มหันตภัยกาแล็กซี`, `ผู้ชี้ทาง`, `หมอกดำ`, `พเนอร์`, `พาร์ทเนอร์`, `rossweisse`, `รอสไวส์`, `รอซึวสึ`, `ross white`, `ross wipe`, `tenebria`, `เทเนเบรีย`, `เนบีย`, `sereniel`, `เซเรเนียล`, `เซรนิว`, `เซรณี` |
| **`Wuthering_Waves.md`** | `wuthering waves`, `wuwa`, `wing wave`, `วิทเทอริ่งเวฟ`, `คลื่นเวฟ`, `ศึกคลื่นคั่ง`, `concerto energy`, `เกจคอนแชร์โต`, `echo system`, `ระบบเอคโค่`, `sonata effect`, `tacet discord`, `solaris-3`, `huanglong`, `rinascita`, `jinhsi`, `จินซี`, `changli`, `ฉางลี่`, `shorekeeper`, `ผู้ดูแลชายฝั่ง`, `xiangli yao`, `เซียงหลี่เหยา` |
| **`Zenless_Zone_Zero.md`** | `zenless zone zero`, `zzz`, `เซนเลส`, `เซนเลสโซนซีโร่`, `new eridu`, `นิวเอริดู`, `hollow zero`, `ฮอลโลว์ซีโร่`, `shiyu defense`, `bangboo`, `แบงบู`, `w-engine`, `ดับเบิลยูเอ็นจิ้น`, `mindscape cinema`, `polychrome`, `โพลีโครม`, `phaethon`, `เฟธอน`, `cunning hares`, `victoria housekeeping`, `section 6`, `sons of calydon`, `hoshimi miyabi`, `tsukishiro yanagi`, `asaba harumasa` |
| **`Genshin_Impact.md`** | `genshin impact`, `genshin`, `เกนชิน`, `เกนชินอิมแพค`, `teyvat`, `เทย์วัต`, `primogem`, `ไพรโมเจม`, `fatui`, `ฟาทุย`, `harbinger`, `celestia`, `เซเลสเทีย`, `abyss order`, `nightsoul`, `วิญญาณราตรี`, `ฟลอจิสตัน`, `natlan`, `นัตลัน`, `nod-krai`, `น็อด-ไกร`, `fontaine`, `sumeru`, `inazuma`, `liyue`, `mondstadt`, `mavuika`, `มาวุยก้า`, `xilonen`, `ชิโลเนน`, `kinich`, `คินิช`, `mualani`, `มัวลานี่`, `neuvillette`, `นิววิลเล็ตต์`, `furina`, `ฟูริน่า`, `nahida`, `นาฮิดะ`, `scaramouche`, `สคารามุช`, `dottore`, `ด็อตโตเร` |
| **`Honkai_Star_Rail.md`** | `honkai star rail`, `hsr`, `star rail`, `รางดาว`, `ฮอนไครางดาว`, `ฮงไกสตาร์เรล`, `astral express`, `ขบวนรถไฟดวงดาว`, `stellar jade`, `หยกดวงดาว`, `light cone`, `ไลท์โคน`, `eidolon`, `simulated universe`, `จักรวาลจำลอง`, `divergent universe`, `apocalyptic shadow`, `memory of chaos`, `pure fiction`, `amphoreus`, `แอมโฟเรียส`, `xianzhou`, `เซียนโจว`, `penacony`, `เพนาโคนี่`, `jarilo-vi`, `belobog`, `phainon`, `ไฟนอน`, `castorice`, `คาสโตริเซ่`, `the herta`, `เฮอร์ต้า`, `aglaea`, `อักลาเอีย`, `tribbie`, `ทริบบี้`, `mydei`, `ไมเดย์`, `anaxa`, `อนักซา`, `feixiao`, `เฟยเซียว`, `jiaoqiu`, `เจียวชิว`, `lingsha`, `ลิงชา`, `acheron`, `อาเคอรอน` |
| **`Honkai_Impact_3.md` / `Part2`** | `honkai impact`, `honkai impact 3`, `honkai impact 3rd`, `hi3`, `สามเค`, `ฮอนไคอิมแพค`, `herrscher`, `แฮชเชอร์`, `stigmata`, `สติกมาต้า`, `elysian realm`, `แดนสวรรค์แห่งอดีต`, `memorial arena`, `schicksal`, `anti-entropy`, `kiana kaslana`, `raiden mei`, `bronya zaychik`, `theresa apocalypse`, `ป้าเทริ`, `senadina`, `เซนาดิน่า`, `thelema`, `เธเลม่า`, `songque`, `ซ่งเชวี่ย` |
| **`Blue_Archive.md`** | `blue archive`, `bluearchive`, `บลูอาร์ไคฟ์`, `บลูอาร์ไคฟ`, `บัวไค`, `บูไค`, `บัวใคร`, `ブルーアーカイブ`, `kivotos`, `คิโวทอส`, `schale`, `ชาเล่ต์`, `pyroxene`, `ไพร็อกซีน`, `เพชรฟ้า`, `eleph`, `เอเลฟ`, `momotalk`, `total assault`, `gematria`, `เกมาเทรีย`, `abydos`, `อะบิดอส`, `gehenna`, `เกเฮนน่า`, `millennium`, `มิลเลนเนียม`, `trinity`, `ทรินิตี้` |
| **`Arknights.md`** | `arknights`, `อาร์คไนท์`, `อาร์กไนท์`, `อาร์กนก`, `rhodes island`, `โรดส์ไอแลนด์`, `originium`, `ออริจิเนียม`, `orundum`, `โอรันดัม`, `integrated strategies`, `contingency contract`, `reclamation algorithm`, `amiya`, `อามิยะ`, `kal'tsit`, `คัลซิท`, `mlynar`, `ลุงมู`, `degenbrecher`, `เจ๊ดาบเดี่ยว`, `eyjafjalla`, `texas the omertosa` |
| **`Arknights_Endfield.md`** | `arknights endfield`, `endfield`, `เอนด์ฟิลด์`, `อาร์คไนท์เอนด์ฟิลด์`, `talos-ii`, `ทาลอสทู`, `endministrator`, `ผู้ควบคุมเอนด์ฟิลด์`, `automated industry complex`, `perlica`, `เพอร์ลิกา`, `คุณเพอร์`, `chen qianyu`, `เฉิน เฉียนยวี่`, `น้องเฉินเด็ก`, `wulfgard`, `วูลฟ์การ์ด`, `laevatain`, `เลวาทีล`, `zhuang fangyi`, `จวงฟางอี้` |
| **`Limbus_Company.md`** | `limbus company`, `limbus`, `ลิมบัส`, `ลิมบัสคอมพานี`, `project moon`, `โปรเจกต์มูน`, `ปูมูน`, `mephistopheles`, `เมฟิสโตเฟลีส`, `lunacy`, `ลูนาซี่`, `mirror dungeon`, `ดันเจี้ยนกระจก`, `sin resonance`, `การสั่นพ้องบาป`, `intervallo`, `yi sang`, `อีซัง`, `ryoshu`, `เรียวชู`, `ป้าเรียว`, `meursault`, `เมอร์โซลต์`, `hong lu`, `ฮงลู`, `heathcliff`, `ฮีธคลิฟฟ์`, `ishmael`, `อิชมาเอล`, `vergilius`, `เวอร์จิลิอุส` |
| **`fgo-knowledge.md` / `atlas_fgo.db`** | `fate grand order`, `fgo`, `grand order`, `เฟทแกรนด์ออเดอร์`, `เล่นเฟท`, `chaldea`, `คาลเดีย`, `saint quartz`, `เพชรสีรุ้ง`, `เพชรเฟท`, `noble phantasm`, `โฮกุ`, `command spell`, `เรจู`, `lostbelt`, `ลอสต์เบลต์`, `ordeal call`, `ออร์ดีลคอล`, `เซอร์แวนท์`, `mash kyrielight`, `มาชู`, `castoria`, `คาสโทเรีย`, `koyanskaya`, `โคยันสกาย่า`, `ashiya douman`, `อาชิยะ โดมัน`, `ereshkigal`, `อิเรชคิกัล` |
| **`Deadlock.md`** | `deadlock`, `เดดล็อก`, `เดดล็อค`, `the patron`, `soul urn`, `ไหวิญญาณ`, `เลนซิปไลน์`, `vindicta`, `วินดิกต้า`, `grey talon`, `เกรย์ ทาลอน`, `lady geist`, `เลดี้ ไกส์ต`, `mcginnis`, `แม็กกินนิส`, `mo & krill`, `โม แอนด์ คริลล์`, `infernus`, `อินเฟอร์นัส`, `bebop`, `บีบ็อป` |
| **`Eternal_Return.md`** | `eternal return`, `อีเทอร์นอลรีเทิร์น`, `black survival`, `lumia island`, `เกาะลูเมีย`, `debby & marlene`, `เด็บบี้ แอนด์ มาร์ลีน`, `เดบิมาเน่`, `xiukai`, `ซิ่วไค` |
| **`Pokemon_PvP.md` / `Radical_Red`** | `pokemon`, `pokémon`, `โปเกมอน`, `โปเกม่อน`, `radical red`, `เรดิคอลเรด`, `pokemon showdown`, `vgc`, `terastal`, `เทรัสทัล`, `trick room`, `ทริครูม`, `pokedex`, `โปเกเด็กซ์`, `pikachu`, `พิคาชู`, `baxcalibur`, `แบกซ์แคลิเบอร์`, `garchomp`, `การ์โชมป์`, `spectrier`, `flutter mane`, `incineroar`, `กาโอกาเอ็น`, `urshifu`, `อูราโอสึ` |
| **`ygo_cards.db`** | `yu-gi-oh`, `yugioh`, `ygo`, `ยูกิโอ`, `การ์ดยูกิโอ`, `ดูเอลลิงก์`, `master duel`, `มาสเตอร์ดูเอล`, `pendulum summon`, `เพนดูลั่ม`, `synchro summon`, `ซิงโคร`, `xyz summon`, `เอ็กซีส`, `link summon`, `blue-eyes white dragon`, `บลูอายส์`, `dark magician`, `exodia`, `เอ็กโซเดีย`, `ash blossom`, `อุราระ`, `maxx c`, `แม็กซ์ซี`, `tearlament`, `เทียร์ลาเมนต์`, `snake-eye` |
| **`Sekiro` / `Zelda` / `Minecraft` / `Dinoblade` / `Heartopia`** | **Sekiro**: `sekiro`, `เซกิโร`, `เซกิโร่`, `shadows die twice`, `ashina`, `อาชินะ`, `shinobi prosthetic`, `แขนกลชิโนบิ`, `mikiri counter`, `มิคิริ`, `dragonrot`, `โรคเลือดมังกร`, `genichiro`, `isshin ashina` · **Zelda**: `zelda`, `เซลด้า`, `breath of the wild`, `tears of the kingdom`, `hyrule`, `ไฮรูล`, `sheikah slate`, `korok seed`, `เมล็ดโคโรค`, `divine beast`, `vah ruta`, `waterblight ganon`, `ganondorf`, `prince sidon`, `เจ้าชายไซดอน`, `mipha` · **Minecraft**: `minecraft`, `ไมน์คราฟต์`, `มายคราฟ`, `cisco rpg`, `ซิสโก้`, `spell wheel`, `forge gem` · **Dinoblade**: `dinoblade`, `ไดโนเบลด`, `parrying extinction`, `spinosaurus sword`, `earthshaker`, `the purple resort`, `ราชันคำสาป` · **Heartopia**: `heartopia`, `ฮาร์ทโทเปีย`, `ฮาร์โทเปีย`, `ฮาโทเปีย`, `心动小镇` |
| **`Bleach` / `Tokusatsu` / `Book Fair`** | **Bleach**: `bleach`, `บลีช`, `เทพมรณะ`, `zanpakuto`, `ดาบฟันวิญญาณ`, `bankai`, `บังไค`, `soul society`, `โซลโซไซตี้`, `gotei 13`, `sternritter`, `kurosaki ichigo`, `คุโรซากิ อิจิโกะ`, `yhwach`, `จูฮาบัช`, `จัวบัส`, `aizen sosuke`, `ไอเซ็น`, `urahara`, `tensa zangetsu`, `kyoka suigetsu`, `the almighty` · **Tokusatsu**: `tokusatsu`, `โทคุซัตสึ`, `โทคุสะสึ`, `ไลฟ์โทกุ`, `คอนเทนต์โทกุ`, `kamen rider`, `คาเมนไรเดอร์`, `มาสค์ไรเดอร์`, `super sentai`, `ขบวนการเซนไต`, `ซุปเปอร์เซนไต`, `ultraman`, `อุลตร้าแมน`, `henshin`, `เฮนชิน`, `เข็มขัดแปลงร่าง`, `เข็มขัดไรเดอร์`, `gavv`, `ไรเดอร์กาฟ`, `gotchard`, `ก็อตชาร์ด`, `geats`, `กีทส์`, `boonboomger`, `บูนบูมเจอร์`, `king-ohger`, `donbrothers`, `project r.e.d.`, `gavan infinity` · **Events**: `งานสัปดาห์หนังสือ`, `งานหนังสือ`, `book expo`, `book fair`, `ศูนย์สิริกิติ์`, `phoenix next`, `siam inter comics`, `dexpress`, `luckpim`, `รักพิมพ์`, `animag`, `อนิแม็ก`, `first page pro`, `bongkoch`, `บงกช`, `zenshu`, `เซนชู`, `lily house`, `kinokuniya`, `animate bangkok`, `maruya`, `มารุยะ`, `comic world`, `japan expo` |

---

## Global Filters (Blocked from Stage-1 Game Voting)

1. **Common Japanese / Western Character Names (`COMMON_CHARACTER_NAMES_BLACKLIST`):**
   - **Japanese Given/Surnames:** `yuki`, `ยูกิ`, `rin`, `ริน`, `mika`, `มิกะ`, `hina`, `ฮินะ`, `yuuka`, `ยูกะ`, `aru`, `อารุ`, `noa`, `โนอา`, `maki`, `มากิ`, `rio`, `ริโอะ`, `mina`, `มินะ`, `saki`, `ซากิ`, `koharu`, `โคฮารุ`, `wakamo`, `kisaki`, `seia`, `shiroko`, `ชิโรโกะ`, `hoshino`, `โฮชิโนะ`, `arona`, `อาโรน่า`, `plana`, `aya`, `อายะ`, `kuro`, `คุโระ`, `kuroko`, `chizuru`, `ชิซุรุ`, `miyabi`, `มิยาบิ`, `yanagi`, `ยานางิ`, `harumasa`, `ฮารุมาสะ`, `yuzuha`, `yamato`, `ยามาโตะ`, `raiden`, `mei`, `เมย์`, `sakura`, `kiana`, `fuji`, `ฟูจิ`, `ayaka`, `yoimiya`, `kokomi`, `kazuha`.
   - **Western / Literary Given Names:** `emma`, `เอ็มม่า`, `lucy`, `ลูซี่`, `รูซี่`, `alice`, `อลิส`, `yvonne`, `อีวอน`, `อีวอนน์`, `rossi`, `รอสซี่`, `diana`, `ไดอาน่า`, `beryl`, `เบริล`, `cassius`, `คาสสิอุส`, `adelheid`, `maribell`, `renoir`, `เลนัว`, `luke`, `ลุค`, `jackie`, `แจ็คกี้`, `charlotte`, `ชาร์ล็อต`, `lenore`, `bianca`, `martina`, `tazia`, `tia`, `nicky`, `นิกิ`, `robin`, `โรบิน`, `sunday`, `ซันเดย์`, `sparkle`, `blade`, `kafka`, `asta`, `lynx`, `hook`, `clara`, `natasha`, `bronya`, `seele`, `theresa`, `vita`, `lantern`, `durandal`, `himeko`, `amber`, `lisa`, `jean`, `mona`, `klee`, `barbara`, `bennett`, `fischl`, `noelle`, `rosaria`, `eula`, `albedo`, `venti`, `cyno`, `nilou`, `dehya`, `lyney`, `navia`, `emilie`, `phoebe`, `ฟีบี้`, `carlotta`, `คาร์ล็อตต้า`, `brant`, `แบรนท์`, `roccia`, `camellya`, `anby`, `burnice`, `caesar`, `jane doe`, `evelyn`, `astra`, `lighter`, `trigger`, `seed`, `ellen`, `grace`, `anton`, `ben`, `lycaon`, `rina`, `corin`, `seth`, `piper`, `nicole`, `billy`, `faust`, `don quixote`, `dante`, `sinclair`, `rodion`, `outis`, `gregor`, `morgan`, `oberon`, `artoria`, `gilgamesh`, `merlin`, `lancelot`, `nero`, `jeanne`, `karna`, `arjuna`, `achilles`, `abrams`, `kelvin`, `warden`, `wraith`, `mirage`, `paradox`, `dynamo`, `lash`, `haze`, `ivy`, `pocket`, `seven`, `shiv`, `viscous`, `link`, `misty`, `brock`, `erika`, `sabrina`, `koga`, `blaine`, `clair`, `may`, `brendan`, `giovanni`.
   - **Why:** These names exist across multiple games and anime. In `signal_detector.py`, any entry in `knowledge.json` or `discover_reference_games()` matching `COMMON_CHARACTER_NAMES_BLACKLIST` is stripped before Stage-1 scoring. Once Stage 1 locks the active game via franchise/mechanic words + chaining weight, Stage 2 (`build_chunk_entity_context`) unlocks the character glossary for that specific game only.

2. **Normal Gaming Standing Words (`GENERIC_GAMING_STANDING_WORDS` + `DUPE_TIER_RE`):**
   - **Dupe / Limit-Break Codes:** `E0`–`E6`, `C0`–`C6`, `S0`–`S6`, `R1`–`R5`, `M0`–`M6`, `U1`–`U5`, `NP1`–`NP5`, `E0S1`, `E2S1`, `E6S5`, `C6R5`, `3–6 ดาว`, `SSR`, `SR`, `UR`.
   - **Generic Gacha / RPG / Combat Words:** `เกม`, `เล่น`, `กาชา`, `เปิดตู้`, `สุ่ม`, `การันตี`, `หลุดเรท`, `เกลือ`, `ดองเม็ด`, `หน้าตู้`, `ซอง`, `แพ็ค`, `เติมเงิน`, `สายฟรี`, `f2p`, `pickup`, `banner`, `recruit`, `spark`, `pull`, `pity`, `บอส`, `มอน`, `ดาเมจ`, `สกิล`, `พาสซีฟ`, `อัลติ`, `อัปเกรด`, `ตัวละคร`, `จัดทีม`, `เมต้า`, `เทียร์ลิสต์`, `การ์ด`, `เด็ค`, `เทิร์น`, `โล่`, `เกราะ`, `คริ`, `บัฟ`, `ดีบัฟ`, `ฮีล`, `แทงค์`, `ซัพพอร์ต`, `ตีบอส`, `one-shot`, `parry`, `ปัดป้อง`, `block`, `บล็อก`, `summon`, `อัญเชิญ`, `skill`, `passive`, `ult`, `boss`, `bosses`, `dps`, `tank`, `support`, `healer`, `solo`, `multiplayer`, `pvp`, `pve`, `endgame`, `normal mode`, `easy mode`, `hardcore mode`, `fate`, `เฟท`, `servant`, `nexon`, `เน็กซอน`.
   - **Markdown Table Metadata (`ENTITY_STOPWORDS`):** `สมาชิก`, `กลไก`, `อดีต`, `ความทรงจำ`, `เล่มจบ`, `ราคา`, `ชื่อเกม`, `ผู้พัฒนา`, `วันวางจำหน่าย`, `แพลตฟอร์ม`, `แนวเกม`, `เนื้อเรื่องย่อ`, `โครงสร้างหลัก`, `ความหมาย`, `จุดเชื่อมโยงสำคัญ`, `protagonist`, `concept`, `content`, `core goal`, `purpose`, `year`, `broadcast`, `format`, `base game`.
   - **Ambiguous Single Words (`AMBIGUOUS_SINGLE_TOKENS`):** `blue`, `thai`, `japan`, `dark`, `super`, `heart`, `dino`, `eternal`, `world`, `star`, `project`, `red`, `nine`, `seven`.

---

## Global Constraints

- Zero external dependencies beyond Python standard library.
- Existing `signals.json` schema keys (`start_sec`, `primary_topic`, `best_file`, `confidence`, `matched_keywords`, `weighted_files`) remain backward-compatible; add `candidates`, `special_keywords`, and `standing_keywords`.
- Chaining decay factor $\alpha = 0.88$; metadata seed multiplier $= 15.0$.
- All existing tests in `skills/anibon-timestamper-local/tests/` must continue to pass.

## Review Focus

1. **Common Japanese Name Collision (`ยูกิ`, `ริน`, `มิกะ`, `โฮชิโนะ`, `ชิโรโกะ`, `มิยาบิ`):** Saying *"แลกยูกิ E3"*, *"ได้ริน"*, *"มิกะ 1 ตัว"* in a CZN stream must **never** score points for Yu-Gi-Oh (`ygo_cards.db`), Blue Archive (`Blue_Archive.md`), Eternal Return (`Eternal_Return.md`), or Fate (`fgo-knowledge.md`) in Stage 1.
2. **Gacha Dupe Shorthand Trap (`C5`, `C6`, `E1`, `E2`, `E6`, `S1`):** Filtered into `standing_keywords`; zero game weight.
3. **Markdown Table Header Leakage (`สมาชิก`, `กลไก`, `เกลือ`, `Normal Mode`, `Parry`):** Filtered out of `parse_markdown_entities()` via `ENTITY_STOPWORDS`.
4. **Silent Gameplay Chunks (0 special words in chunk):** Chained weight $W_t(g) = 0.88 \cdot W_{t-1}(g)$ keeps CZN as the top candidate across chunks where Boat only says generic standing words or common character first names.
5. **True Mid-Stream Game Switch:** Sustained Stage-1 special words from a second game ($\ge 2$ consecutive chunks) cross over the decaying weight of the first game.

---

### Task 1: Per-Game Special Words Registry, Common-Name Blacklist, Standing-Word Filter & CZN Roster Expansion

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/signal_detector.py:76-106`
- Modify: `skills/anibon-timestamper-local/scripts/anibon/knowledge_reader.py:19-130`
- Modify: `skills/anibon-world-identity/references/Chaos_Zero_Nightmare.md:11-80`
- Test: `skills/anibon-timestamper-local/tests/test_signal_detector.py`
- Test: `skills/anibon-timestamper-local/tests/test_knowledge_reader.py`

**Interfaces:**
- Produces:
  - `GAME_SPECIAL_WORDS: dict[str, list[str]]` in `signal_detector.py`
  - `COMMON_CHARACTER_NAMES_BLACKLIST: set[str]`, `AMBIGUOUS_SINGLE_TOKENS: set[str]`, `GENERIC_GAMING_STANDING_WORDS: set[str]`, `DUPE_TIER_RE: re.Pattern` in `signal_detector.py`
  - `filter_standing_gaming_words(text: str) -> tuple[str, list[str]]` in `signal_detector.py`
  - `ENTITY_STOPWORDS: set[str]` in `anibon/knowledge_reader.py`

- [ ] **Step 1: Write failing tests in `test_signal_detector.py` and `test_knowledge_reader.py`**

In `skills/anibon-timestamper-local/tests/test_signal_detector.py`:
```python
    def test_filter_standing_gaming_words_strips_dupe_codes_and_generic_terms(self):
        from signal_detector import filter_standing_gaming_words
        raw = "เปิดกาชา ตัวใหม่ C5 E6 S1 บอส ดาเมจ รอซึวสึ พเนอร์ โอเมก้าโค้ด"
        filtered, standing = filter_standing_gaming_words(raw)
        self.assertIn("c5", standing)
        self.assertIn("e6", standing)
        self.assertIn("s1", standing)
        self.assertNotIn(" c5 ", f" {filtered} ")
        self.assertNotIn(" e6 ", f" {filtered} ")
        self.assertIn("รอซึวสึ", filtered)
        self.assertIn("พเนอร์", filtered)
        self.assertIn("โอเมก้าโค้ด", filtered)

    def test_discover_reference_games_registers_special_words_and_blocks_common_character_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            refs = Path(tmp) / "references"
            refs.mkdir()
            for fn in ("Blue_Archive.md", "Chaos_Zero_Nightmare.md", "Wuthering_Waves.md", "Zenless_Zone_Zero.md", "Eternal_Return.md", "Thai_Book_Fair_Convention.md"):
                (refs / fn).write_text(f"# {fn}\n", encoding="utf-8")

            discovered = discover_reference_games(refs)
            for blocked in ("blue", "thai", "parry", "solo", "เกลือ", "yuki", "ยูกิ", "rin", "ริน", "mika", "มิกะ", "hoshino", "shiroko", "arona", "lucy", "alice", "yvonne", "kuro", "emma", "chizuru"):
                self.assertNotIn(blocked, discovered)
            for czn_kw in ("เคอส", "รอซึวสึ", "พเนอร์", "memory fragment", "โอเมก้าโค้ด", "เซรนิว"):
                self.assertIn("chaos_zero_nightmare", discovered[czn_kw].lower())
            self.assertIn("wuthering_waves", discovered["jinhsi"].lower())
            self.assertIn("zenless_zone_zero", discovered["bangboo"].lower())
            self.assertIn("blue_archive", discovered["kivotos"].lower())
```

In `skills/anibon-timestamper-local/tests/test_knowledge_reader.py`:
```python
    def test_parse_markdown_entities_excludes_generic_standing_words_but_keeps_characters_for_stage2(self):
        from anibon.knowledge_reader import parse_markdown_entities
        md = (
            "- **สมาชิก**: Maribell + Diana\n"
            "- **กลไก**: ใช้โล่สะท้อนดาเมจ\n"
            "- **เกลือ**: สุ่มไม่ติดหน้าตู้\n"
            "- **Parry (ปัดป้อง)**: กดกันจังหวะศัตรูตี\n"
            "- **Normal Mode**: โหมดปกติ\n"
            "- **E1**: ปลดล็อคขั้น 1\n"
            "- **Yuki (ยูกิ)**: ตัวละครสายโจมตี\n"
            "- **Rossweisse (รอสไวส์)**: ตัวละครใหม่\n"
        )
        ents = parse_markdown_entities(md)
        for generic in ("สมาชิก", "กลไก", "เกลือ", "Parry", "Normal Mode", "E1"):
            self.assertNotIn(generic, ents)
        self.assertIn("Yuki", ents)
        self.assertIn("Rossweisse", ents)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=skills/anibon-timestamper-local/scripts pytest skills/anibon-timestamper-local/tests/test_signal_detector.py skills/anibon-timestamper-local/tests/test_knowledge_reader.py -v`
Expected: FAIL (`ImportError: cannot import name 'filter_standing_gaming_words'`).

- [ ] **Step 3: Implement `GAME_SPECIAL_WORDS`, `COMMON_CHARACTER_NAMES_BLACKLIST`, `filter_standing_gaming_words()`, `ENTITY_STOPWORDS`, and expand `Chaos_Zero_Nightmare.md`**

1. In `skills/anibon-timestamper-local/scripts/signal_detector.py`:
   - Add `GAME_SPECIAL_WORDS` mapping each reference filename to the Stage-1 Exclusive Special Words table.
   - Add `COMMON_CHARACTER_NAMES_BLACKLIST`, `AMBIGUOUS_SINGLE_TOKENS`, `GENERIC_GAMING_STANDING_WORDS`, `DUPE_TIER_RE`, and `filter_standing_gaming_words()`.
   - Update `discover_reference_games()` to register `GAME_SPECIAL_WORDS` for existing files in `refs_dir` and strip any key in `AMBIGUOUS_SINGLE_TOKENS | COMMON_CHARACTER_NAMES_BLACKLIST | GENERIC_GAMING_STANDING_WORDS`.
2. In `skills/anibon-timestamper-local/scripts/anibon/knowledge_reader.py`:
   - Filter out `ENTITY_STOPWORDS` and `DUPE_TIER_RE` inside `parse_markdown_entities()` while keeping character names (`Yuki`, `Rin`, `Mika`, `Rossweisse`) for Stage-2 scoped lookup.
3. In `skills/anibon-world-identity/references/Chaos_Zero_Nightmare.md`:
   - Add **Rossweisse (รอสไวส์ / รอซึวสึ)**, **Yuki (ยูกิ)**, **Rin (ริน)**, **Yvonne (อีวอนน์)**, **Nebia (เนเบีย / เนบีย)**, **Sereniel (เซเรเนียล / เซรนิว / เซรณี)**, **Renoir (เรนัวร์ / เลนัว)**, **Mika (มิกะ)**, **Partner (พาร์ทเนอร์ / พเนอร์)**, **Memory Fragment (เมมโมรี่แฟรกเมนต์)**, and **Omega Code (โอเมก้าโค้ด)**.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=skills/anibon-timestamper-local/scripts pytest skills/anibon-timestamper-local/tests/test_signal_detector.py skills/anibon-timestamper-local/tests/test_knowledge_reader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/signal_detector.py \
        skills/anibon-timestamper-local/scripts/anibon/knowledge_reader.py \
        skills/anibon-world-identity/references/Chaos_Zero_Nightmare.md \
        skills/anibon-timestamper-local/tests/test_signal_detector.py \
        skills/anibon-timestamper-local/tests/test_knowledge_reader.py
git commit -m "feat(signal): add per-game special word registry and block common character names in stage 1"
```

---

### Task 2: Chaining Weight Engine on Special Words in `signal_detector.py`

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/signal_detector.py:236-389`
- Test: `skills/anibon-timestamper-local/tests/test_signal_detector.py`

**Interfaces:**
- Consumes: `filter_standing_gaming_words()`, `discover_reference_games()`, `extract_metadata_signals()`, `COMMON_CHARACTER_NAMES_BLACKLIST`
- Produces:
  - `detect_signals_for_chunks(workspace: Path, knowledge_path: Optional[Path] = None, chain_decay: float = 0.88) -> dict`
  - Emits per-chunk `"special_keywords": list[str]`, `"standing_keywords": list[str]`, and `"candidates": list[dict]`.

- [ ] **Step 1: Write failing tests for special-word chaining weight & common-name immunity in `test_signal_detector.py`**

```python
    def test_chaining_weight_ignores_common_japanese_names_and_standing_dupe_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "info.json").write_text(json.dumps({
                "title": "1 ปีแล้ว ของ ฝันร้าย",
                "description": "เล่น Chaos Zero Nightmare",
                "tags": ["CZN"]
            }, ensure_ascii=False), encoding="utf-8")
            chunks = ws / "chunks"
            chunks.mkdir()
            (chunks / "chunk_00.txt").write_text("สวัสดีครับ วันนี้มาเล่น Chaos Zero Nightmare ครบรอบ 1 ปี", encoding="utf-8")
            (chunks / "chunk_01.txt").write_text("เปิดกาชา ได้ยูกิ E3 ได้ริน ได้มิกะ C5 E6 S1 เกลือมาก ตีบอส", encoding="utf-8")
            (chunks / "chunk_02.txt").write_text("อัปเกรดพเนอร์ รอซึวสึ โอเมก้าโค้ด เมมโมรี่แฟรกเมนต์", encoding="utf-8")

            signals = detect_signals_for_chunks(ws)
            self.assertIn("chaos_zero_nightmare", signals["chunk_01"]["best_file"].lower())
            self.assertNotIn("ยูกิ", signals["chunk_01"]["matched_keywords"])
            self.assertIn("e6", signals["chunk_01"]["standing_keywords"])
            self.assertIn("chaos_zero_nightmare", signals["chunk_02"]["best_file"].lower())
            self.assertIn("รอซึวสึ", signals["chunk_02"]["special_keywords"])
            self.assertGreater(signals["chunk_02"]["candidates"][0]["prob"], 0.85)

    def test_chaining_weight_switches_on_sustained_new_game_special_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            chunks = ws / "chunks"
            chunks.mkdir()
            (chunks / "chunk_00.txt").write_text("เล่น Chaos Zero Nightmare ตีบอส เคอส", encoding="utf-8")
            (chunks / "chunk_01.txt").write_text("เปลี่ยนเกมมาเล่น Deadlock กับ Vindicta และ Grey Talon ใน Deadlock", encoding="utf-8")
            (chunks / "chunk_02.txt").write_text("Deadlock ตานี้ Bebop เก็บไหวิญญาณสวยมาก เล่น Deadlock ยาวๆ", encoding="utf-8")

            signals = detect_signals_for_chunks(ws)
            self.assertIn("chaos_zero_nightmare", signals["chunk_00"]["best_file"].lower())
            self.assertIn("deadlock", signals["chunk_02"]["best_file"].lower())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=skills/anibon-timestamper-local/scripts pytest skills/anibon-timestamper-local/tests/test_signal_detector.py -v`
Expected: FAIL (`"ยูกิ"` currently in `matched_keywords`, `KeyError: 'standing_keywords'`).

- [ ] **Step 3: Implement Stage-1 blacklist pruning and forward chaining weight in `detect_signals_for_chunks()`**

In `skills/anibon-timestamper-local/scripts/signal_detector.py`:
1. After merging `load_knowledge()` and `discover_reference_games()`, prune any entry key where `kw.lower() in (COMMON_CHARACTER_NAMES_BLACKLIST | AMBIGUOUS_SINGLE_TOKENS | {"fate", "เฟท", "servant", "nexon", "เน็กซอน"})`.
2. For each chunk, run `filtered_text, standing_kws = filter_standing_gaming_words(raw_text.lower())`.
3. Compute `raw_specific_scores` only for entries with `kind in specific_kinds` and `kw.lower() not in GENERIC_GAMING_STANDING_WORDS`.
4. Seed `chained_game_weights` from `meta_signals` ($\times 15.0$) and update sequentially:
   `chained_game_weights[f] = chain_decay * chained_game_weights.get(f, 0.0) + raw_specific_scores.get(f, 0.0)`
5. Store `special_keywords`, `standing_keywords`, and `candidates` (sorted by chained weight with normalized `prob`) in `signals[cid]`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=skills/anibon-timestamper-local/scripts pytest skills/anibon-timestamper-local/tests/test_signal_detector.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/signal_detector.py \
        skills/anibon-timestamper-local/tests/test_signal_detector.py
git commit -m "feat(signal): chain game weights on special words and strip common character names in stage 1"
```

---

### Task 3: Candidate Weight + Standing-Word / Common-Name Guard in `prompts.py`

**Files:**
- Modify: `skills/anibon-timestamper-local/scripts/anibon/prompts.py:93-169,196-285`
- Test: `skills/anibon-timestamper-local/tests/test_prompts.py`

**Interfaces:**
- Consumes: `signal["candidates"]`, `signal["special_keywords"]`, `signal["standing_keywords"]` from Task 2.
- Produces:
  - `build_candidate_weights_block(signal: Optional[dict]) -> str` in `anibon/prompts.py`
  - `build_chunk_entity_context(chunk_text: str, glossary: Optional[dict] = None, max_tokens: int = ENTITY_CONTEXT_MAX_TOKENS, allowed_sources: Optional[set[str]] = None) -> str`

- [ ] **Step 1: Write failing tests in `skills/anibon-timestamper-local/tests/test_prompts.py`**

```python
    def test_build_recursive_prompt_injects_candidate_weights_and_standing_word_guard(self):
        chunk = {
            "_idx": 17,
            "items": [{"timestamp": "01:16:36", "start": 4596.0, "text": "ตัวใหม่ C5 เปิดพเนอร์ รอซึวสึ E2"}]
        }
        signal = {
            "best_file": "../anibon-world-identity/references/Chaos_Zero_Nightmare.md",
            "primary_topic": "Chaos Zero Nightmare",
            "confidence": 0.91,
            "special_keywords": ["พเนอร์", "รอซึวสึ"],
            "standing_keywords": ["c5", "e2"],
            "candidates": [
                {"file": "Chaos_Zero_Nightmare.md", "topic": "Chaos Zero Nightmare", "weight": 34.2, "prob": 0.91, "keywords": ["พเนอร์", "รอซึวสึ"]},
            ],
        }
        prompt = build_recursive_prompt(
            chunk=chunk,
            current_topic="เล่น Chaos Zero Nightmare",
            rolling_summary="ปู่โบ๊ตเปิดกาชา",
            lang="th",
            signal=signal,
        )
        self.assertIn("CANDIDATE DOMAIN WEIGHTS", prompt)
        self.assertIn("Chaos Zero Nightmare: weight=34.2 (91%)", prompt)
        self.assertIn("พเนอร์, รอซึวสึ", prompt)
        self.assertIn("GENERIC GAMING STANDING WORDS", prompt)
        self.assertNotIn("e.g. Wuthering Waves", prompt)

    def test_build_chunk_entity_context_filters_by_allowed_sources(self):
        glossary = {
            "Yuki": {"th": "ยูกิ", "role": "Striker", "source_file": "Chaos_Zero_Nightmare.md"},
            "Hoshino": {"th": "โฮชิโนะ", "role": "Tank", "source_file": "Blue_Archive.md"},
        }
        ctx = build_chunk_entity_context("ยูกิ กับ โฮชิโนะ", glossary, allowed_sources={"Chaos_Zero_Nightmare.md"})
        self.assertIn("Yuki", ctx)
        self.assertNotIn("Hoshino", ctx)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=skills/anibon-timestamper-local/scripts pytest skills/anibon-timestamper-local/tests/test_prompts.py -v`
Expected: FAIL (`CANDIDATE DOMAIN WEIGHTS` not found).

- [ ] **Step 3: Implement `build_candidate_weights_block()` and `allowed_sources` scoping in `prompts.py`**

In `skills/anibon-timestamper-local/scripts/anibon/prompts.py`:
1. Add `allowed_sources: Optional[set] = None` to `build_chunk_entity_context()`.
2. Implement `build_candidate_weights_block(signal: Optional[dict]) -> str` displaying candidate weights, matched special words, and the `GENERIC GAMING STANDING WORDS & COMMON NAMES` guard (instructing the LLM never to infer another game from `E0–E6`/`C0–C6` or shared character names like `Yuki`, `Rin`, `Mika`, `Yvonne`).
3. Remove hardcoded `Wuthering Waves` examples from `build_recursive_prompt()` and `build_group_prompt()`.

- [ ] **Step 4: Run full test suite to verify all tests pass**

Run: `PYTHONPATH=skills/anibon-timestamper-local/scripts pytest skills/anibon-timestamper-local/tests/ -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/anibon-timestamper-local/scripts/anibon/prompts.py \
        skills/anibon-timestamper-local/tests/test_prompts.py
git commit -m "feat(prompts): inject special-word candidate weights and common-name/standing-word guard"
```

---

### Task 4: Re-generate `signals.json` & Verify on Workspace `jduUyRfQwss`

**Files:**
- Modify: `~/youtube_jduUyRfQwss_workspace/signals.json` (generated)
- Modify: `~/youtube_jduUyRfQwss_workspace/entity_glossary.json` (generated)

- [ ] **Step 1: Regenerate `signals.json` and `entity_glossary.json` on `~/youtube_jduUyRfQwss_workspace` and verify chunks 12, 17–21, 56–62**

Run:
```bash
python3 - <<'EOF'
import sys
from pathlib import Path
sys.path.insert(0, "/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/scripts")
from signal_detector import detect_signals_for_chunks
from process_chunks_local import run_knowledge_discovery

ws = Path("/Users/zenithth/youtube_jduUyRfQwss_workspace")
s = detect_signals_for_chunks(ws)
run_knowledge_discovery(ws, s)

for cid in ["chunk_12", "chunk_17", "chunk_18", "chunk_21", "chunk_56", "chunk_57", "chunk_58", "chunk_61"]:
    c = s[cid]
    top = c["candidates"][0] if c.get("candidates") else {}
    print(f"{cid}: best={Path(c['best_file']).name} prob={top.get('prob')} special={c.get('special_keywords')} standing={c.get('standing_keywords')[:5]}")
EOF
```
Expected: All inspected chunks resolve to `Chaos_Zero_Nightmare.md` with `prob >= 0.85` and zero false `ygo_cards.db` / `Blue_Archive.md` matches.

- [ ] **Step 2: Smoke-test `chunk_12` (`--max-chunks 13`) and launch detached run for `chunk_13`..`chunk_108`**

Run:
```bash
python3 -X utf8 /Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/scripts/process_chunks_local.py \
  ~/youtube_jduUyRfQwss_workspace \
  --mode recursive --lang th --endpoint "http://100.115.25.30:1234/v1/chat/completions" --max-chunks 13 && \
/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper-local/scripts/launch_local.zsh \
  ~/youtube_jduUyRfQwss_workspace \
  100.115.25.30 auto th recursive "https://www.youtube.com/watch?v=jduUyRfQwss"
```
Expected: `chunk_12` outputs pure CZN timestamps; detached process resumes from `chunk_13`.
