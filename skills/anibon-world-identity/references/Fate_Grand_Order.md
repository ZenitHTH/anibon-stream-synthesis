# ⚔️ Fate/Grand Order (FGO / เฟทแกรนด์ออเดอร์) - Deep Knowledge Base

คู่มืออ้างอิงข้อมูลเชิงลึกเนื้อเรื่องหลัก ระบบการต่อสู้ เมต้า และประวัติศาสตร์เวอร์ชันอัปเดตล่าสุดของเกม **Fate/Grand Order (FGO — เซิร์ฟเวอร์ญี่ปุ่น JP)** สำหรับใช้ประกอบการทำไทม์สแตมป์สตรีมช่อง Anibon Official

> **หมายเหตุสำคัญ (JP Server Focus):** ปู่โบ๊ตเล่นและติดตามข่าวสาร **เซิร์ฟเวอร์ญี่ปุ่น (FGO JP)** เป็นหลัก ชื่อเซอร์แวนท์ อีเวนต์ และระบบใหม่ทั้งหมดจึงอ้างอิงตามกำหนดการและชื่อภาษาญี่ปุ่น/สากลของเซิร์ฟเวอร์ JP เป็นแกนกลาง (อัปเดตล่าสุด: **19 พฤศจิกายน 2026**)
> **ฐานข้อมูล SQLite คู่ขนาน:** ข้อมูล Master Data ครบทุกตัวละคร อีเวนต์ ไอเทม และ CE เก็บอยู่ใน `skills/reference/FGO and DATA/atlas_fgo.db` (ดูคู่มือคิวรีใน [`FGO_DB_Reference.md`](FGO%20and%20DATA/FGO_DB_Reference.md) และกฎการเรียกชื่อใน [`fgo-knowledge.md`](../../../references/stream/fgo-knowledge.md))

## 🔥 สถานะแพตช์ล่าสุด (Current Live Patch)
- **อีเวนต์ปัจจุบัน (11 พ.ย. – 2 ธ.ค. 2026):** **GUDAGUDA Puni-Puni Wars! (กุดากุดะ ปูนิปูนิ วอร์ส / สเปเชียลชุดว่ายน้ำกลางฤดูหนาว)** ณ ซิงกูลาริตี้ GUNMA
- **ตู้กาชาใหม่ล่าสุด (16 พ.ย. 2026):** **Dynamite Rikyu (ไดนาไมต์ ริคิว / เซ็น โนะ ริคิว ว่ายน้ำ / Cutie Koma)** — Foreigner 5★ (#487, QABBB, โฮกุ Buster ST ล้างบัฟป้องกัน & ตีพิเศษ `[Man]` + ทีมปะทะคำสาป)
- **บัฟล่าสุด (18 พ.ย. 2026):** **Sen no Rikyu (เซ็น โนะ ริคิว / ยาย Berserker 5★)** อัปเกรดสกิล 3 เป็น `A+` (Quick แปะคำสาป + แจกบัฟตีพิเศษ `[Curse]` ให้ทั้งทีม)
- **ตัวละครประจำอีเวนต์:** **Himiko and Iyo (ฮิมิโกะ และ อิโยะ)** Pretender 5★, **Saika Magoichi (ไซกะ มาโกอิจิ)** Rider 4★, **Matsunaga Hisahide (มัตสึนางะ ฮิซาฮิเดะ / ดันโจ)** Berserker 4★ Welfare
- **คำศัพท์ ASR / สแลงช่อง:** `ยาย` / `ริคิว` = Sen no Rikyu / Dynamite Rikyu, `โคมะฮิเมะ` / `Cutie Koma` = Komahime, `ทำนา` = ฟาร์มเพชร/บอนด์/เรด

---

## 🗓️ ทำเนียบรุ่นและประวัติการอัปเดต (Chronological Version & Servant History: Oldest to Latest)

### 📌 ยุคคลาสสิกถึงบทส่งท้ายภาค 2 (Part 1 – Part 2 Final Chapter [2015 – ต้นปี 2026])
*ภาพรวมเส้นเวลาเนื้อเรื่องหลักของ FGO ก่อนก้าวเข้าสู่บทใหม่ **one second after time** ในปี 2026*

*   **Part 1 — Observer on Timeless Temple:** ริทสึกะ ฟูจิมารุ และมาชู คิริเอไลท์ เดินทางผ่าน **7 Singularities** (Fuyuki, Orleans, Septem, Okeanos, London, America, Camelot, Babylonia) เพื่อหยุดยั้ง Goetia (Beast I) ณ วิหารกาลเวลา
*   **Part 1.5 — Epic of Remnant:** การเก็บกวาด 4 จุดผกผันย่อย (*Shinjuku*, *Agartha*, *Shimousa*, *Salem*)
*   **Part 2 — Cosmos in the Lostbelt:** โลกถูกฟอกขาว เผชิญหน้า 7 แดนสูญพันธุ์ (**Lostbelts 1–7**: Anastasia ถึง Nahui Mictlan) ผ่านยาน Shadow Border / Storm Border
*   **Ordeal Call (奏章 I–IV) & Final Chapter:** บททดสอบเพื่อรับรองการใช้งานคลาสพิเศษ (Extra Classes: Ruler, Avenger, Alter Ego, Moon Cancer) นำไปสู่บทส่งท้ายภาค 2 (*Final Chapter*) และการเปิดระบบ **Grand Servant / Grand Score / Grand Duel** (เช่น *Grand Ego Tamamo-no-Mae*, *Ciel*)
*   **Early 2026 (ก.พ. – พ.ค. 2026):** อีเวนต์ *After Time Valentine 2026*, *CBC 2026*, *Antiochia* และเปิดตัวเซอร์แวนท์ Collection No. 460–469 ได้แก่ **Maris Chaldeas (#460)**, **Lord Logres (#461)**, **Hanasaka no Okina (#462)**, **Hebi Nyōbō (#463)**, **Flora (#464)**, **Demeter (#465)**, **Jacques de Molay [Saber] (#466)**, **François Prélati (#467)**, **Hippolyta (#468)** และ **John Lackland (#469)**

---

### 📌 ยุคปัจจุบัน: Part 3 "one second after time" & อีเวนต์ปี 2026 (มิ.ย. 2026 – พ.ย. 2026 [Oldest → Latest])

| แพตช์ / วันที่ (JP) | ตัวละครใหม่ (En / ไทย) | คลาส / ระดับ / เด็ค | ประเภทโฮกุ / คุณลักษณะ | รายละเอียดอัปเดต เนื้อเรื่อง และเมต้า |
| :--- | :--- | :---: | :---: | :--- |
| **2026.06 (3 มิ.ย. 2026)** | **Urðr (เอิร์ด / อูลูร์)** | Archer 5★ / QAAAB | Arts AoE / Sky | **Part 3 "one second after time" บทที่ 1: Past Chaldea (郷愁永巡刻盤 パスト･カルデア)** ย้อนรอย Orleans ศตวรรษที่ 15; ชื่อแฝง Doomsday Archer (`終末のアーチャー`); โฮกุ `Urðarþráður Forn` สะสมสแต็ก `[Past Alteration]` (สูงสุด 10) และลดเกจชาร์จศัตรู, สกิลล้างบัฟศัตรู/ดีบัฟทีม & ลด CD; พร้อมอัปเกรดแอนิเมชันและบัฟสกิล+โฮกุให้ **David (3★ Archer)**, วัตถุดิบใหม่ `創生の真珠` & `黎溟琥珀`, ระบบ **Recommended Support Setup**, และกลาง มิ.ย. รีรันล่วงหน้า *Enma-tei* |
| **2026.07 (1 ก.ค. 2026)** | **Ascalaphus (อัสคาลาพอส)** | Alter Ego 5★ / QQAAB | Arts AoE / Sky | อีเวนต์ **"Waiting for You at the End of Spring" (春の終わりに君を待つ)**; โฮกุ `Prominima Ti Satihias` ทำดาเมจพิเศษตามดีบัฟลดต้านทาน Instant Death (และติดตายทันที 2 ชั้นบนฟิลด์ `[Hell]`); สกิล 3 แจก Guts 3 ครั้ง + Buff Removal Resist 100% + บัฟพลัง & ชาร์จ NP 50% แลกกับการเสียชีวิตอัตโนมัติหลังครบ 3 เทิร์น |
| **2026.07 (1 ก.ค. 2026)** | **Gray Lily (เกรย์ ลิลี่)** | Saber 4★ / QAABB & Lancer 4★ / QQABB | Buster AoE / Buster ST / Man | เซอร์แวนท์แจกฟรี (Welfare) ประจำอีเวนต์เดือน ก.ค. ผู้เล่นเลือกสายคลาสได้ระหว่าง **Saber** (`Excalibur Logos` — Buster AoE ฟาร์มหมู่) หรือ **Lancer** (`Rhongomyniad Mythos` — Buster ST ล้างบัฟป้องกันและโจมตีพิเศษใส่ `[Servant]`) |
| **2026.08 (2 ส.ค. 2026)** | **Hassan-i Sabbah (อัซราเอล / ฮัสซัน ซับบาห์)** | Assassin 5★ / QAABB | Arts ST / Man | **ฉลองครบรอบ 11 ปี (11th Anniversary — Chaldea Academy Festival ณ Makuhari Messe)**; ร่างหนุ่มยุคเผยแผ่ศาสนาของ First Hassan (Azrael / `アズライール`); โฮกุ `Mal'ak al-Mawt` (Arts ST) ตีแรงขึ้นตามสถานะ `[Thirst for Death]` (死の渇き) พร้อมโอกาส Instant Death และ**รีชาร์จ NP เมื่อสังหารทันทีสำเร็จ**; สกิล 2 `Thirty Birds A` ลด CD สกิลตนเอง 2 เทิร์น; ระบบใหม่ **ขยายเพดาน Bond Lv. 15 → 16**, **เพดาน Fou เป็น 3,000**, ดันเจียนถาวร **Azrael's Temple (アズライールの廟)**, ชุดมาสเตอร์ **Chaldea Academy Uniform**, ตู้ Destiny Order & GSSR และ **Strengthening Quests Part XX (14 ตัวละคร 3–9 ส.ค.)** |
| **2026.08 (12 ส.ค. 2026)** | **Beni-Enma (เบนิเอ็นมะ ร่างซัมเมอร์)** | Berserker 5★ / QAABB | Arts ST / Earth | **Summer 2026: Chaldea Great Southern Sea Showdown! ~Majimun Island~ (カルデア南海大決戦！)** Wave 1; โฮกุ `Contented Stomach of the Ten Kings - Wicker Box's Sea Banquet` (Arts ST) |
| **2026.08 (12 ส.ค. 2026)** | **Kingprotea (คิงโพรเทีย ร่างซัมเมอร์)** | Moon Cancer 5★ / QABBB | Buster AoE / Earth | **Summer 2026 Wave 1**; โฮกุ `Daibotchi King Dive` (Anti-World Buster AoE) แปลงร่างไคจู/ดาบยักษ์ถล่มเกาะทางใต้ |
| **2026.08 (12 ส.ค. 2026)** | **Biscione (บิชโชเนะ ร่างซัมเมอร์)** | Caster 4★ / QAAAB | Arts AoE / Earth | **Summer 2026 Wave 1**; โฮกุ `Draconic Spartoi` (Arts Anti-Army AoE) |
| **2026.08 (15–18 ส.ค. 2026)** | **Habetrot (ฮาเบทร็อต ร่างซัมเมอร์)** | Pretender 4★ / QQABB | Buster AoE / Earth | **Summer 2026 Welfare (แจกฟรี)**; โฮกุ `Chibirā Sanu Habetrot` (Anti-Kaiju Buster) ขึ้นขับหุ่นยักษ์ปะทะภัยคุกคามแห่งเกาะมาจิมุน |
| **2026.08 (18 ส.ค. 2026)** | **Lilith (ลิลิธ ร่างซัมเมอร์)** | Rider 5★ / QQAAB | Quick ST / Earth | **Summer 2026 Wave 2**; โฮกุ `Se'arah Na'arat Fullburn` (Quick ST) สายซิ่งลูกผสมดาเมจ/ซัพพอร์ต |
| **2026.08 (18 ส.ค. 2026)** | **Kingprotea Alter (คิงโพรเทีย ออลเตอร์)** | Avenger 5★ / QABBB | Buster AoE / Earth | **Summer 2026 Wave 2**; โฮกุ `Rākṣasa King Pit` (Buster Anti-Army AoE) ร่างออลเตอร์สายคลั่งแห่งมาจิมุน |
| **2026.08 (18 ส.ค. 2026)** | **Ono-no-Komachi (โอโนะ โนะ โคมาจิ ร่างซัมเมอร์)** | Archer 4★ / QQAAB | Quick / Sky | **Summer 2026 Wave 2**; โฮกุ `Impressions of Evil Karma - Dharma King Enma` (Anti-Sin Quick) พร้อมคอสตูมฤดูร้อนสำหรับ **Bedivere**, **Dante Alighieri** และ **Hassan of the Shining Star** |
| **2026.09 (16 ก.ย. 2026)** | **Daedalus (ไดดาลอส)** | Berserker 5★ / QAABB | Buster AoE / Man | **ฉลอง 35M DL (2–16 ก.ย. แจกตั๋ว 4★ ฟรี 130 ตัว + 30 SQ)** ต่อด้วย **Halloween 2026: Drop Dead! Pumpkin Farm Slaughter (くたばれ！ パンプキンファーム・スローター, 16 ก.ย.–7 ต.ค.)**; โฮกุ `Ikaros Ascends Again` (Buster AoE ลด DEF, ล้างดีบัฟทีม & ฮีล 2,000); สกิล 1 ลด CD เพื่อน 1 เทิร์น + ชาร์จ 30% + บัฟ A/B, สกิล 2 บัฟ OC ทีม & บัฟตามการ์ดตี, สกิล 3 ชาร์จตัวเอง 50%; คอสตูมฮาโลวีน 6 ตัว (Jack, Baobhan Sith, Tsuna, Tutankhamun, Kukulkan, Jekyll) และ Rank Up **Shuten-Dōji (Caster)** + **Kashin Koji (22 ก.ย.)** |
| **2026.10 (23 ต.ค. 2026)** | **Tamamo Aria (ทามาโมะ อาเรีย)** | Rider 5★ / QQAAB | Arts AoE / Earth | **Waxing Moon Rerun (*Fate/Samurai Remnant*, 14 ต.ค.–4 พ.ย.)** บัฟสกิล **Miyamoto Musashi (Saber)** 16 ต.ค. (เพิ่ม NP 30%, บัฟ Buster 3 ครั้ง 3 เทิร์น, OC+2) ตามด้วย **Grand Substitute Battle: Tamamo Aria (冠位名代戦：タマモアリア, 23 ต.ค.–11 พ.ย.)** ศึกบอสทีม Extra ล้วนเพื่อ**ขยายสล็อต Extra Class Grand Servant จาก 2 → 4 ช่อง**; โฮกุ `Kaibou Isshou - Kuudon Kaiki` (Arts AoE) แปะ `[Prohibited Resistance]`, ล้างบัฟโจมตีศัตรู, ตีแรงพิเศษใส่ศัตรูติดดีบัฟจิตใจ, ชาร์จ 50% (+เพิ่มบนฟิลด์ City) และ Rank Up ตระกูลทามาโมะ 3 ตัว; ปิดเดือนด้วยแคมเปญ **FGO THE DRAMALOGUE** (30 ต.ค.) |
| **2026.11 (11 พ.ย. 2026 - LIVE)** | **Himiko and Iyo (ฮิมิโกะ และ อิโยะ)** | Pretender 5★ / QAABB | Arts AoE / Earth | **ฉลอง 100 ล้านดาวน์โหลดทั่วโลก (7–20 พ.ย. 2026: แจกตั๋วเลือก 5★ ฟรี 43 ตัว + ตู้ Merlin)** และ **Midwinter Swimsuit Special: GUDAGUDA Puni-Puni Wars! ~The Lowest Bomb Girl in History~ (11 พ.ย.–2 ธ.ค., พื้นที่ Singularity GUNMA)**; โฮกุ `超古代巨神・埴輪ノッブ` (Arts AoE) ตีพิเศษ `[Demonic]` + ลดต้านทาน Arts/Buster + ชาร์จ NP ทีม + OC+1 + บัฟ Extra Card ทีม; สกิล 1 & 2 ล็อก/แจกไพ่ใหม่ (`コマンドカードを配り直す`), สกิล 3 บัฟคริ & ExtraCard; มาพร้อม QoL หน้าจอรอบซ้ำจำสถานะแถบ **Spoils (戦利品)** และปรับหน้าจอ **Angel's Bazaar** |
| **2026.11 (11 พ.ย. 2026 - LIVE)** | **Saika Magoichi (ไซกะ มาโกอิจิ ร่างไรเดอร์)** | Rider 4★ / QQAAB | Quick AoE / Man | **GUDAGUDA Puni-Puni Wars! (Pickup 1, 11 พ.ย.–2 ธ.ค.)**; ร่างชุดว่ายน้ำของไซกะ มาโกอิจิ; โฮกุ `銃神・ヤタガラスMG-01` (Quick AoE) มอบ Sure Hit 1 เทิร์น + บัฟ Quick 3 เทิร์น + ตีพิเศษใส่ศัตรูสาย `[Sky]` + บัฟ Critical Strength ทั้งทีม 50% (3 เทิร์น); สกิลสนับสนุน Quick/Arts ทีม + ชาร์จตัวเอง 30% + ผลิตดาว |
| **2026.11 (11 พ.ย. 2026 - LIVE)** | **Matsunaga Hisahide (มัตสึนางะ ฮิซาฮิเดะ / มัตสึนางะ ดันโจ)** | Berserker 4★ / QAABB | Buster AoE / Man | **GUDAGUDA Puni-Puni Wars! Welfare (แจกฟรีหลังจบเรด)**; จอมโจรวางระเบิดกาน้ำชา Hiragumo; โฮกุ `ビッグバン・DAN・ジョー！` (Buster AoE) ล้างบัฟป้องกันศัตรูทั้งหมด + ตีพิเศษใส่ `[Lawful]` + **เสียชีวิตทันทีหลังปล่อยโฮกุ (Arash-style Bomber)**; สกิล 3 `真瓦津日 C` มีลูกเล่นทอยลูกเต๋า D20 ลุ้นบัฟสุ่มระดับทีม; มาพร้อมคอสตูมใหม่สำหรับ **Takasugi Shinsaku ("Summer's Kiheitai")** และ **Matsunaga Hisahide** |
| **2026.11 (16–18 พ.ย. 2026 - LIVE)** | **Dynamite Rikyu (ไดนาไมต์ ริคิว / เซ็น โนะ ริคิว ร่างว่ายน้ำ / Cutie Koma)** | Foreigner 5★ / QABBB | Buster ST / Man | **GUDAGUDA Puni-Puni Wars! ตู้พิเศษ Pickup (16 พ.ย.–2 ธ.ค.)**; ร่างชุดว่ายน้ำของ **Sen no Rikyu / Komahime** (#487) ที่เปลี่ยนชื่อและรูปแบบแอนิเมชันตามขั้นร่าง; โฮกุ Buster ST ล้างบัฟป้องกัน + ตีพิเศษใส่ `[Man]` + ลดต้านทาน Buster และคอมโบคำสาป; ต่อเนื่องด้วย **Strengthening Quest (18 พ.ย.)** อัปเกรดสกิล 3 ของ **Sen no Rikyu (Berserker 5★)** เป็น `A+` (Quick แปะคำสาปและแจกบัฟตีพิเศษ `[Curse]` 20–30% ให้ทั้งทีม 3 เทิร์น) |

---

### 📌 เนื้อหาและตู้กาชาที่กำลังจะมาถึง (Upcoming Schedule — ปลาย พ.ย. – ธ.ค. 2026)

| ช่วงเวลา | อีเวนต์ / ตู้กาชาที่กำลังจะมาถึง | ตัวละคร & ฟีเจอร์สำคัญ | รายละเอียดเพิ่มเติม |
| :--- | :--- | :--- | :--- |
| 13 พ.ย. – 2 ธ.ค. 2026 | **GUDAGUDA Puni-Puni Wars Pickup 2 (ตู้ที่สอง กุดากุดะ ปูนิปูนิ วอร์ส)** | Takasugi Shinsaku (Archer 5★), Saitō Hajime (Saber 4★), Okita Sōji Alter (Saber 5★), Okita J Sōji (Assassin 4★) | ตู้รีรันขุนพล GUDAGUDA คู่ขนานชุดคอสตูมว่ายน้ำของทากาสุงิ |
| 14 พ.ย. 2026 | **GUDAGUDA Raid Battles (ด่านเรด กุดากุดะ ปูนิปูนิ วอร์ส)** | Matsunaga Hisahide (ปลดล็อกถาวร) | เปิดด่านเรดรวมพลังชุมชนหลังเคลียร์บทที่ 9 เพื่อปลดล็อกมัตสึนางะถาวร |
| ธ.ค. 2026 – ต้นปี 2027 | **Christmas 2026 and Winter Roadmap (คริสต์มาสและแผนงานฤดูหนาว)** | 100M DL SSR Deadline (31 ธ.ค.), Chaldea Academy Winter Camp | สิ้นสุดเดดไลน์ภารกิจเปลี่ยนตัว SSR ฟรีเป็นถาวร (Lv.60 + Bond 5), อีเวนต์คริสต์มาส 2026 หลังจบ GUDAGUDA และความคืบหน้าบท *one second after time* ตอนถัดไป |

---

## 🧩 ทำเนียบเซอร์แวนท์และคำศัพท์สำคัญ (Entity Glossary for Stream Timestamps)

### ตัวละครและเซอร์แวนท์เด่นปี 2026 (2026 Debut & Key Cast)
- **Dynamite Rikyu (ไดนาไมต์ ริคิว / Cutie Koma / เซ็น โนะ ริคิว ว่ายน้ำ)**: Foreigner 5★ (Collection No. 487) ร่างชุดว่ายน้ำของ Sen no Rikyu / Komahime เปิดตัว 16 พ.ย. 2026 ในอีเวนต์ GUDAGUDA ปูนิปูนิ วอร์ส โฮกุ Buster ST ตีพิเศษสาย Man และเล่นคอมโบคำสาป
- **Sen no Rikyu (เซ็น โนะ ริคิว / ยาย / โคมะฮิเมะ)**: Berserker 5★ ที่ได้รับ Rank Up สกิล 3 (18 พ.ย. 2026) แปะคำสาปจากการตี Quick และแจกบัฟตีพิเศษใส่ศัตรูติดคำสาปให้ทั้งทีม
- **Himiko and Iyo (ฮิมิโกะ และ อิโยะ)**: Pretender 5★ (Collection No. 484) คู่หูราชินีแห่งยามาไตในอีเวนต์ GUDAGUDA พ.ย. 2026 โฮกุ Arts AoE โยนไพ่ใหม่และบัฟ Extra Attack
- **Himiko (ฮิมิโกะ)**: ราชินีแห่งยามาไต จับคู่กับอิโยะในคลาส Pretender 5★ (GUDAGUDA พ.ย. 2026) และได้รับบัฟอัปเกรดในแคมเปญ Strengthening Part XX (7 ส.ค. 2026)
- **Iyo (อิโยะ)**: มิโกะผู้สืบทอดของฮิมิโกะ ร่วมทีมในคลาส Pretender 5★ (GUDAGUDA พ.ย. 2026)
- **Saika Magoichi (ไซกะ มาโกอิจิ)**: Rider 4★ (Collection No. 485) ร่างชุดว่ายน้ำ GUDAGUDA พ.ย. 2026 โฮกุ Quick AoE ตีพิเศษสาย Sky และบัฟคริทีม
- **Matsunaga Hisahide (มัตสึนางะ ฮิซาฮิเดะ)**: Berserker 4★ Welfare (Collection No. 486) หรือ มัตสึนางะ ดันโจ โฮกุ Buster AoE สละชีพแบบอาราชและสกิลทอยเต๋า D20
- **Matsunaga Danjo (มัตสึนางะ ดันโจ)**: อีกชื่อเรียกของมัตสึนางะ ฮิซาฮิเดะ ตัวละครแจกฟรีประจำ GUDAGUDA พ.ย. 2026
- **Takasugi Shinsaku (ทาคาสุงิ ชินซากุ)**: Archer 5★ รับชุดคอสตูมฤดูหนาว-ชุดว่ายน้ำ "Summer's Kiheitai" และขึ้นตู้ Pickup 2 พ.ย. 2026
- **Saito Hajime (ไซโต้ ฮาจิเมะ)**: Saber 4★ ตัวละครเด่นในตู้ Pickup 2 ของอีเวนต์ GUDAGUDA พ.ย. 2026
- **Okita Souji Alter (โอคิตะ โซจิ ออลเตอร์)**: Saber 5★ ตัวละครเด่นในตู้ Pickup 2 ของอีเวนต์ GUDAGUDA พ.ย. 2026
- **Tamamo Aria (ทามาโมะ อาเรีย)**: Rider 5★ (Collection No. 483) หนึ่งใน Tamamo Nine เปิดตัวในศึก Grand Substitute Battle ต.ค. 2026 โฮกุ Arts AoE แปะดีบัฟจิตใจและขยายสล็อต Grand Extra
- **Daedalus (ไดดาลอส)**: Berserker 5★ (Collection No. 482) นักประดิษฐ์ผู้สร้างปีกอิคารอส เปิดตัวในอีเวนต์ฮาโลวีน 2026 โฮกุ Buster AoE ซัพพอร์ตลด CD และล้างดีบัฟทีม
- **Miyamoto Musashi (มิยาโมโตะ มูซาชิ)**: Saber 5★ ได้รับอัปเกรดสกิล 1 (Heavenly Eye A+) เพิ่มชาร์จ NP 30%, บัฟ Buster 3 ครั้ง 3 เทิร์น และ OC+2 ในรีรัน Samurai Remnant ต.ค. 2026
- **Azrael (อัซราเอล)**: ชื่อเรียกยอดนิยมของ Hassan-i Sabbah ร่างหนุ่ม (Assassin 5★, Collection No. 474) เซอร์แวนท์ครบรอบ 11 ปี
- **Hassan-i Sabbah (ฮัสซัน ซับบาห์)**: Assassin 5★ (Collection No. 474) เซอร์แวนท์ครบรอบ 11 ปี (ส.ค. 2026) ร่างหนุ่มของปู่คิง โฮกุ Arts ST รีชาร์จเมื่อ Instant Death สำเร็จ
- **Beni-Enma (เบนิเอ็นมะ)**: Berserker 5★ (Collection No. 475) เซอร์แวนท์ซัมเมอร์ 2026 Wave 1 เกาะมาจิมุน โฮกุ Arts ST
- **Kingprotea (คิงโพรเทีย)**: Moon Cancer 5★ (Collection No. 476) เซอร์แวนท์ซัมเมอร์ 2026 Wave 1 โฮกุ Buster Anti-World
- **Biscione (บิชโชเนะ)**: Caster 4★ (Collection No. 477) เซอร์แวนท์ซัมเมอร์ 2026 Wave 1 โฮกุ Arts AoE
- **Lilith (ลิลิธ)**: Rider 5★ (Collection No. 478) เซอร์แวนท์ซัมเมอร์ 2026 Wave 2 โฮกุ Quick ST
- **Kingprotea Alter (คิงโพรเทีย ออลเตอร์)**: Avenger 5★ (Collection No. 479) เซอร์แวนท์ซัมเมอร์ 2026 Wave 2 โฮกุ Buster AoE
- **Ono-no-Komachi (โอโนะ โนะ โคมาจิ)**: Archer 4★ (Collection No. 480) เซอร์แวนท์ซัมเมอร์ 2026 Wave 2 โฮกุ Quick Anti-Sin
- **Habetrot (ฮาเบทร็อต)**: Pretender 4★ Welfare (Collection No. 481) เซอร์แวนท์แจกฟรีซัมเมอร์ 2026 โฮกุ Buster Anti-Kaiju
- **Ascalaphus (อัสคาลาพอส)**: Alter Ego 5★ (Collection No. 471) เปิดตัว ก.ค. 2026 โฮกุ Arts AoE สาย Instant Death และสกิลสละชีพ 3 เทิร์น
- **Gray Lily (เกรย์ ลิลี่)**: Saber 4★ / Lancer 4★ Welfare (Collection No. 472–473) ร่างวัยเยาว์ของเกรย์ เลือกคลาสได้ระหว่าง Excalibur Logos กับ Rhongomyniad Mythos
- **Urd (เอิร์ด)**: Archer 5★ (Collection No. 470, Urðr) ชื่อแฝง Doomsday Archer เปิดตัวบท Past Chaldea มิ.ย. 2026
- **Doomsday Archer (อาร์เชอร์แห่งวันสิ้นโลก)**: ชื่อชั่วคราวก่อนเปิดเผยตัวจริงของ Urðr ในบท Past Chaldea มิ.ย. 2026
- **Kashin Koji (คาชิน โคจิ)**: Assassin 5★ ได้รับบัฟสกิล Mystic Eyes of Spider (22 ก.ย. 2026) เปลี่ยนเป็นติด Bound หมู่และชาร์จ NP สูงสุด 20% ต่อตัว
- **Shuten-Doji Caster (ชูเทน โดจิ แคสเตอร์)**: Caster 4★ ได้รับการอัปเกรดสกิลช่วงก่อนอีเวนต์ฮาโลวีน ก.ย. 2026

### ระบบเกมเพลย์ โหมดระดับสูง และคำศัพท์เฉพาะ (Core Systems & Lore)
- **Past Chaldea (พาสต์ คาลเดีย)**: บทที่ 1 ของ Part 3 "one second after time" เดินทางย้อนกลับไปกู้ประวัติศาสตร์ ณ ออร์เลออง ศตวรรษที่ 15
- **Grand Substitute Battle (แกรนด์ ซับสติทิวท์)**: ศึกบอสและเรดท้าทายเงื่อนไขพิเศษ (`冠位名代戦` เช่น Extra-only ของ Tamamo Aria) เพื่อปลดล็อกขยายสล็อต Extra Class Grand Servant จาก 2 เป็น 4 ช่อง
- **Bond 16 (บอนด์สิบหก)**: การปลดล็อกเพดานเลเวลสายสัมพันธ์จาก 15 เป็น 16 พร้อมเพดาน Fou 3,000 ในการอัปเดตครบรอบ 11 ปี
- **100 Million Downloads Worldwide (แคมเปญหนึ่งร้อยล้านดาวน์โหลด)**: แคมเปญฉลองพร้อมกันทั่วโลก พ.ย. 2026 แจกตั๋วเลือก 5★ ฟรี 43 ตัวละครถึง Ordeal Call II
- **GUNMA Singularity (กันมะ ซิงกูลาริตี้)**: ฉากหลังพิศวงของอีเวนต์ GUDAGUDA พ.ย. 2026 (`特N型生命圏 GUNMA`) ที่มีหมู่บ้านน้ำพุร้อนฤดูร้อนซ่อนตัวกลางภูเขาหิมะ
- **GUDAGUDA Puni-Puni Wars (กุดากุดะ ปูนิปูนิ วอร์ส)**: อีเวนต์พิเศษฤดูหนาวชุดว่ายน้ำ ประจำเดือน พ.ย. 2026

---

## ⚙️ จุดควรระวังเชิงฐานข้อมูลและระบบ (Database & Logic Pitfalls)

1. **Card Enum Mapping (Atlas Academy JSON):** ใน `nice_servant` ของ Atlas Academy ตัวเลขการ์ดคำสั่งและโฮกุคือ **`1` = Arts**, **`2` = Buster**, **`3` = Quick** (อย่าสลับ `1` กับ `3`)
2. **True Name Revelation (`svtChange`):** ตัวละครบางตัวในเนื้อเรื่องหลัก (เช่น `終末のアーチャー` / Doomsday Archer) จะเก็บชื่อจริง (`ウルズ` / Urðr) ไว้ใน `basic_servant.originalName` ขณะที่ชื่อแฝงก่อนเปิดเผยตัวจริงอยู่ใน `svtChange`
3. **Provisional Joining (仮加入) ในตั๋วเลือกฟรี 2026:** ทั้งตั๋ว 4★ (35M DL) และตั๋ว 5★ (100M DL พ.ย. 2026) ตัวละครที่เลือกจะเข้าทีมแบบชั่วคราวก่อน และต้องอัปเลเวลถึง **Lv. 60 + Bond Lv. 5** ภายใน **31 ธ.ค. 2026** (สำหรับ 100M DL) จึงจะคงอยู่ถาวร
4. **JP vs. Localizations:** ตัวละครที่เพิ่งลง JP ช่วงปลายปี 2026 (เช่น `ダイダロス`, `タマモアリア`, `卑弥呼＆壱与`, `松永久秀`) ยังแสดงชื่อเป็นภาษาญี่ปุ่นในฟิลด์ `name` ของ API อังกฤษจนกว่าเซิร์ฟเวอร์ NA จะแปลอย่างเป็นทางการ

---

## 🔗 แหล่งอ้างอิง (References)
- [Fate/Grand Order Official JP News](https://news.fate-go.jp/) — ประกาศแพตช์ ตู้กาชา และ QoL อย่างเป็นทางการของเซิร์ฟเวอร์ JP
- [Atlas Academy DB (JP)](https://apps.atlasacademy.io/db/JP) — ฐานข้อมูลสกิล โฮกุ ค่าตัวเลข และ Master Data เซิร์ฟเวอร์ JP
- [Fate/Grand Order Wiki (Fandom)](https://fategrandorder.fandom.com/wiki/Fate/Grand_Order_Wiki) — สรุปอีเวนต์ แบนเนอร์ และประวัติอัปเดตย้อนหลัง
- [`fgo-knowledge.md`](../../../references/stream/fgo-knowledge.md) — กฎการสะกดชื่อไทย/ญี่ปุ่น และศัพท์สแลงช่อง Anibon Official
