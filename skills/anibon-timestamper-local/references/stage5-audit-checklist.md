# Stage 5 Local-Model Timestamp & Audit Checklist

Run this full audit on **both** `anibon_timestamps.md` and `all_timestamps.txt` after Pass 2 completes and before delivering output.

## 1. World Identity & Stream Title Grounding
- **Load `anibon-world-identity`**: Verify all emitted names against local ground truth:
  - **FGO**: Query `atlas_fgo.db` (do not confuse Ashiya Douman with Ascalon/Asclepius).
  - **Pokémon**: Query `pokemon.db`; enforce Thai name first (`ชื่อไทย (English Name)`, e.g. `แบกซ์แคลิเบอร์ (Baxcalibur)`).
  - **Anime / Gacha / Competitive**: Verify against `skills/anibon-world-identity/references/*.md` (e.g. `Chaos_Zero_Nightmare.md`, `Genshin_Impact.md`, `Honkai_Star_Rail.md`, `Wuthering_Waves.md`) and patch notes for new titles (e.g. Deadlock heroes: Baba Yaga, Celeste, Abrams).
  - **Unindexed Indie / Web / Thai Games** (e.g. *1 in 8 Billion*, *1 ชีวิต ณ กรุงศรี*, *หนึ่งในอสงไขย*): Scaffold `references/<Topic>.md` first, then reconstruct timestamps from `raw_transcript.json`.
- **Stream Title Token Priority**: Proper nouns, mod names, and franchises in `info.json` title/description override ASR phonetic truncations (snap `Vity` → `Verity`, `Nania` → `Narnia`).

## 2. Mandatory LiveChat `[t-30s, t+90s]` & Dual-Side Mood Cross-Check
Never audit from ASR `chunks/` alone. Inspect `livechat_events.txt` around `[t-30s, t+90s]` for every non-trivial `[Talk]`/`[Gacha]`/`[Reaction]` stamp:
- **Misheard Foreign Titles**: Trust exact title spellings typed by chat over ASR approximations (`"เกอบังคาย"` → *BanG Dream! Our Note*, not *Blue Archive*; `"เรา Kingdom"` → *Three Kingdoms (สามก๊ก)*, not manga *Kingdom*).
- **Live Viewer Corrections (`t+30s..t+90s`)**: Check 60–90s past a claim to see if chat corrected Boat and he confirmed (e.g. *Orbitals* did get Art Direction nom; *DK Bananza* base game was last year so debate is about its DLC).
- **Anti-Bleed & Visual Grounding Guard**: When a suspect unit/boss appears invented (`Ziongo`, `Nobunaga Audi Eternity`) or missing from `atlas_fgo.db` (NPC-only Servants like `Matsunaga Hisahide`), inspect `chunks/*.txt` dialogue and exact `frames/chunk_tiles/tile_*.jpg` before trusting chat chatter (`Enkidu` in chat can bleed onto active `Sakata Kintoki`).
- **Dual-Side Mood**: Cross-check `LiveChat Highlights` and `mood_555.json` (`MEME_PULSE`, `SHOCK_HYPE_PULSE`) so high-energy peaks are not flattened into dry monologues.

## 3. Full-Stream Timing & Boundary Verification (No Suspect-Only Audit)
Do **not** audit only chunks flagged for ASR/glossary warnings — unread continuation chunks and chunk tails hide topic shifts and 1–3 min timing drift:
- **Chunk-Cutoff Boundary Audit**: Check every stamp within `±15s` of a chunk `start` or `cutoff=` boundary (e.g. `00:22:30`, `02:30:00`). Read `90–180s` of the prior chunk tail and rewind to the opening sentence where the topic began.
- **Lead-In Anchor (Start vs. Punchline)**: Every `HH:MM:SS` must anchor to the opening transition cue (`เดี๋ยวคุยเรื่อง...`, `มาฝั่ง...`), not a mid-segment reaction/punchline 1–3 minutes later.
- **WatchParty Player-Bar Spot Check**: Open `frames/slides_clean/slide_*.jpg` for `[WatchParty]` starts and showcase pivots to confirm the embedded video/tab opens at the emitted `HH:MM:SS`.
- **Discord Guest Join & Leave**: Preserve both mic-join and sign-off timestamps (never swallowed by `SAME_TOPIC`).
- **100% Every-Stamp Transcript+LiveChat Sweep**: Dump `[-60s, +35s]` of deduplicated `chunks/*.txt` + `livechat_events.txt` for **every** emitted timestamp in `anibon_timestamps.md` (not only flagged lines). Verify: (1) primary subject matches both speech and chat (if a title conflicts with chat, inspect `raw_transcript.json` to rule out a poisoned `garbled_replacements.json` rule), (2) `HH:MM:SS` hits the opening cue rather than a repeat 2–6 min later, and (3) `00:00:00`–`chunk_02` has no `[Talk]` hallucinated during Pre-Roll BGM.
- **Single-Frame Visual Title Verification**: When Boat browses lists/pages or WatchParty episodes and ASR/local model garbles the title/episode, extract frames with `ffmpeg -ss <HH:MM:SS> -i video_360p.mp4 -frames:v 1` and delegate reading them to a `research` (`Model: "flash"`) subagent (returns text-only facts, keeping images out of main context).

## 4. Local-Model Distortion & Dual-Track Audit
- **Domain Context Bleeding**: Check non-gaming talk adjacent to gaming segments; verify the true subject in `raw_transcript.json` so `"บริษัทนั้น"` in food/politics is not distorted into `"บริษัทเกม"`.
- **Comparative Analogy Promotion & Off-Hand Analogy Rule**: Frame stamps around the primary subject when a secondary work (*Heaven Burns Red*, *Yu-Gi-Oh! GX*, *Bleach*, *Frieren*) appears only for 1–2 sentences of comparison inside another review (*Wuthering Waves*, *One Punch Man S3*).
- **Gameplay vs. Gacha & Catalyst vs. Banner Target**: Watch for pull keywords (`หลุดเรท`, `ตู้ถาวร`, `เพชรหมด`, `Token Exchange`) so gacha pulls are not mislabeled as ongoing mechanics. Distinguish My Room catalyst/meme (`Nobunaga`) from actual banner target (`Dynamite Rikyu`).
- **Critique-Clause Verdict Polarity**: Never invert mixed praise-with-caveat remarks into bashing from one isolated clause (`"อยากให้ X ได้... มันก็ดี แต่เล่นไม่กี่รอบก็เบื่อ"` defends/regrets *X* losing). Confirm stance with LiveChat.
- **Award WatchParty Acronyms**: Cross-check phonetic acronyms (`"f z"` / `"PBZ"` → *Phantom Blade Zero*, not *F-Zero*; `"C of RAM"` → *Cult of the Lamb*) against verified nominee lists in `references/*.md`.
- **3-Second Chat Dismissal Promotion**: If a game title matches a chat reply dismissed in 1–2 sentences (`"ช่างแม่ง"`), check the next 30–60s and restore the ongoing primary subject.
- **Dual-Track Desync (Gameplay State vs. Talk Topic)**: When Boat sets up an ongoing action (mob fights, AFK farms, crafts, boss waits) and talks about unrelated topics for 5–40 min:
  1. *Gameplay Track*: Search backward up to ~20 min for intent verbs (`เดี๋ยวให้มันสู้กัน`, `รอ`, `ปล่อยไว้`, `เสก`, `ล่อ`) and verify storyboard quest/boss HUD + mobs.
  2. *Talk Track*: Identify what Boat is speaking about (donations, news, Q&A).
  3. *Label Rule*: Emit one stamp naming both tracks (talk tag when speech dominates, game state as context, e.g. `[Talk] เฝ้า <Mob_A> สู้กับ <Mob_B> พร้อมถกประเด็น <Topic>`), then close the arc with a payoff stamp when resolved.
- **Premature `[Victory]` Lookahead**: Read `30–60s` forward around every `[Victory]` stamp (`"ผ่านแล้ว"` → `"อ้าว ไม่ผ่าน"`) and verify destination cues (`"ไปชั้น 13 ได้"` means Floor **12** cleared).
- **Pre-Roll, `[Donation]`, `[Ending]` & Rage-Quit**:
  - *Pre-Roll*: Stamp `00:00:00 - [Intro]` when chunk 00 starts with waiting BGM/`[เพลง]` before Thai speech; never invent anime titles from BGM. When `chunk_00`–`chunk_02` contain only non-Thai BGM lyrics (`가끔하라고`, `미라와`, etc.) before Boat greets viewers (`สวัสดีทุกคน`), delete any Pass-1 `[Talk]` stamps hallucinated from livechat during those BGM chunks and anchor the first `[Talk]` to Boat's actual mic entry.
  - *Outro & EOF-Stranded `[Ending]`*: Scan the final 3–5 minutes for closing tokens (`ขอบคุณครับ`, `ลงไลฟ์`, `ราตรีสวัสดิ์`, `บ๊ายบาย`), separate `[Donation]` donor-list/birthday shoutouts, and rewind `[Ending]` if stranded in the last ~30s.
  - *Strict Truth on `[Ending]`*: Never emit `"แจ้งกำหนดการสตรีมถัดไป"` unless Boat explicitly states the next stream time/topic in the final 3–5 minutes of `chunks/`.
  - *22:00 Routine & Rage-Quit*: Map `"ไลฟ์โทกุ"` ASR drifts (`โทกกู`, `ทั่วกุ`, `คอนเทนทุกคึ`) to `โทคุซัตสึ (Tokusatsu)`, never *Tokyo Ghoul*. On abrupt crash/rage-quit (`พอ`, `เลิก`, `ไม่ไหวแล้ว`, `ปิดไลฟ์`), anchor `[Ending]` to the quit moment.
- **Custom-Avatar Donation Popups**: Do not label 3D/figure donation alert popups as literal product reviews or showcases (`[Talk] โชว์ฟิกเกอร์`); confirm in `livechat_events.txt` and `chunks/*.txt`.
- **Game-Switch Carryover & Unmentioned Lore**: Never attribute a previous game's endgame mechanics (`"หอรี"`, `"เฟ้อกว่าเวเนซุเอลา"`) to a newly booted game, and reject unmentioned franchise lore (`"Lostbelt"`) hallucinated from pre-training when absent from `chunks/*.txt` and `livechat/`.

## 5. Style, Conciseness & Verb Diversity
- **Conciseness & Sharpness (50–65 Thai Chars Target)**: Keep each line to **1 core claim + concrete entities** (`~50–65` Thai chars, 8–16 words, 95-char max): `[Action/Verb] <Entity/Topic> + <Specific Angle/Verdict>`. Hard-trim filler (`เรื่องการ...`, `พร้อมทั้ง...`, `เพื่อความสมดุลและน่าสนใจ`, `ที่ทำให้...`, `โดยมีการ...`, `ในเกม`).
- **No Bundled Mashups**: Give separate timestamps when named games/news items start `≥ 2 min` apart (`00:30:40` OoT vs `00:33:47` Fire Emblem; `00:40:50` DK DLC vs `00:43:30` PS/Wolverine).
- **No Vague Abstractions**: Replace generic lines (`"วิพากษ์ความเหลื่อมล้ำ..."`, `"ผลงานของ CloverWorks"`) with named games, studios, or stats (`Metacritic 99`, `30 FPS`, `GamingDose`, `Studio Bind`, `Toaru Item`, `Olga Marie`).
- **Clean Prefixes/Suffixes**: Never start lines/part titles with `'ปู่โบ๊ต'`, embed bracketed times (`[01:23:45]`, `จากภาพในจอ`), prepend repetitive `"เฝ้าสำรวจ <Game> พร้อม..."` prefixes, or append redundant `'ใน <Title>'` suffixes.
- **Opening-Verb Saturation (`"วิพากษ์"` Check)**: Local 12B models overuse `"วิพากษ์"` (40%+). Verify every opening verb stays `≤ 20%` of total lines and never repeats `> 2` consecutive lines.

## 6. Domain Traps & `reaction_verify_log.json` Audit
- **FGO & Store ASR Homophones / Idioms**: `MP1`–`MP5` → `NP1`–`NP5`; `ซีบอ` → `CE บอนด์`; `แคสเลีย` → `แคสทอเรีย (Castoria)`; `ลิคิว` → `ริคิว (Sen no Rikyu)`; `1 ก.` / `10 ก.` → `1 โรล` / `10 โรล`; `คิวตรวจสตรีมล้น` → **Steam** review queue (not livestream); `"ชุดวันเกิด"` → `"ชุดพื้นฐาน (ชุดวันเกิด)"`, never `"เวอร์ชั่น Naked"`.
- **Tokusatsu Stage Show & TTFC Traps**: Stage show forms (`Chaos Drone`, `Extra Shadow`, `Advance`) are not gacha games (*Chaos Zero Nightmare*); ASR `"ชิรูบิ"` → `ไรเดอร์ชิโนบิ (Kamen Rider Shinobi)`; `Today is Friday in California` → actor `Hiroshi Tsuchida`; `Shu Watanabe` (Kamen Rider OOO) is not `Gojo Satoru`; *Armor Hero* is live-action Tokusatsu, not anime.
- **Yuri False Friend**: `"เผด็จการยูริ"` in anime/gaming streams refers exclusively to ***The Great Villainess: Strategy of Lily***, never *Red Alert 2: Yuri's Revenge*.
- **Royal / Monarchy Safety (`masking-royal-news`)**: Scan all part headers and stamps in both `anibon_timestamps.md` and `all_timestamps.txt` for direct royal names, `สถาบันพระมหากษัตริย์`/`สถาบันฯ`/`ราชวงศ์`, royal initiatives (e.g., *To Be Number One*), or Section 112 in royal context. When triggered, mask with `masking-royal-news` metaphors in both files (general political party or academic 112 lawfare commentary stays unmasked per skill rules).
- **ASR False-English Homophones**: Check odd literal English nouns in Thai political/pop-culture stamps against `chunks/` + `livechat/` (`"The Bag"` → `"เดอะแบก"`, `"Double Door"` → `"ดัมเบิลดอร์ (Dumbledore)"`, `"ไอ้รัชนก"` → `"ไอซ์ รัชนก"`), and inspect `git diff resources/garbled_replacements.json` if `garbled_collector` auto-imported a misheard English phrase.
- **Pass-2 Rewrites (`reaction_verify_log.json`)**: Compare accepted `updated` entries against original Pass-1 lines, `chunks/*.txt`, and `livechat/`. Reject speculative proper nouns, invented third-person names, character misattribution, or `[Talk]`/`[Gameplay]` explanations flipped into `[Reaction]`; ensure sudden shock peaks (`"What?!"`) are not absorbed 20–30s late.

## 7. Dual-File Sync, Gate Re-Run & Knowledge Harvesting
1. **Verify Pruning & Sync Both Files**: Confirm `anibon_timestamps.md` is pruned to essential milestones (`~40–60` stamps; if `prune_essential()` silently fell back to the full unpruned list, manually prune micro-talk stamps first). Apply every fix to both `anibon_timestamps.md` (`anibon_timestamps_essential.md`) and `all_timestamps.txt` (`anibon_timestamps_full.md`, plus `timestamp_<VID>.md` if backed up).
2. **Re-Run Root Gates** (live at plugin root `scripts/`, not skill `scripts/`):
   ```bash
   python3 scripts/audit_gaps.py ~/youtube_<VIDEO_ID>_workspace/anibon_timestamps.md --chunks-dir ~/youtube_<VIDEO_ID>_workspace/chunks
   python3 scripts/audit_gaps.py ~/youtube_<VIDEO_ID>_workspace/all_timestamps.txt --chunks-dir ~/youtube_<VIDEO_ID>_workspace/chunks
   python3 scripts/check_sections.py ~/youtube_<VIDEO_ID>_workspace/anibon_timestamps.md
   ```
   *(If running `validate_tags.py`, treat `*_validated.txt` as advisory only — never blindly overwrite `anibon_timestamps.md`, as keyword rules can false-trigger `[Victory]` or `[FanMeet]` on Thai talk lines.)*
3. **Persist Knowledge**: Review `audit_timestamps_against_glossary` warnings; add confirmed drifts via `python3 skills/cleaning-auto-transcripts/scripts/update_garbled_dictionary.py --add "<Target>" "<noise>"`; scaffold new games in `skills/anibon-world-identity/references/<Game>.md` + `INDEX.md`; update live-service patches; and for multi-part numbered series append/update `## Stream Chronology & Play History` with 5 dimensions: (1) ประเด็นพูดคุย & ดราม่า, (2) ปัญหา Hardware & Engine, (3) ระบบเกม บิลด์ & อุปกรณ์, (4) การสำรวจ & เควสต์, (5) บอสและศึกสำคัญ.
