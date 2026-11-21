---
title: "Anibon Stream & Engineering Wiki — Overview"
category: "overview"
updated: "2026-11-21"
tags: ["overview", "synthesis"]
status: "active"
---

# Anibon Stream & Engineering Wiki — Overview

วิกินี้เป็นคลังความรู้สะสมระยะยาว (Compounding Knowledge Base) ระดับ **Heavy Tier** ของโปรเจกต์ `anibon-stream-synthesis` ครอบคลุมสตรีมของ **`ปู่โบ๊ต` (ANIBON)** จำนวน **210 ไลฟ์สตรีม (ม.ค. 2025 – 21 พ.ย. 2026)** และเอกสารวิศวกรรมของระบบ **Python Pipeline (16 หน้า)**

---

## 1. แกนเนื้อหาไลฟ์สตรีมปู่โบ๊ต & จักรวาลเกม (210 Streams · `2025-01` ถึง `2026-11`)

### เกมกาชา & RPG (`28` เกมหลักใน [[index]])
- **เสาหลักฝั่ง Type-Moon & HoYoverse**:
  - [[fate-grand-order]] (`91` สตรีม): ตั้งแต่ยุคต้น 2025 ถึง [[stream-cqll7dq35bw]] — เน้นความรักในเนื้อเรื่อง, [[sen-no-rikyu]] (จนปลดล็อก NP5 สำเร็จ), [[aoko-aozaki]], [[castoria]], [[lilith-fgo]], [[artoria]], และ [[morgan]] พร้อมข้อสรุปว่า FGO อยู่รอดด้วยศรัทธาแม้ไม่มีหอ Endgame.
  - [[zenless-zone-zero]] (`37` สตรีม) & [[honkai-star-rail]] (`54` สตรีม) & [[genshin-impact]] (`44` สตรีม): ติดตามแพตช์ [[hoyoverse]] ยาวถึง ZZZ 3.4 *The Finality of the Day* ที่เปิดตัว Void Hunter [[sunbringer]] พร้อมคอลแลบ [[kafka]], [[robin]] และ [[jing-yuan]] ใน HSR Apocalyptic Shadow รวมถึง [[firefly]], [[sunday]], [[castorice]], [[phainon]], [[miyabi]], [[ellen-joe]].
- **Project Moon & กาชารุ่นใหม่**:
  - [[limbus-company]] (`52` สตรีม): วิเคราะห์เนื้อเรื่อง Canto/Walpurgis Night, [[yi-sang]], [[faust]], [[don-quixote]], และค่าย [[project-moon]].
  - [[wuthering-waves]] (`54+` สตรีม — รวม [[chisa]]), [[arknights]] (`36` สตรีม — รวม [[talulah]] & Endfield), [[blue-archive]] (`25`), [[nikke]] (`20`), [[chaos-zero-nightmare]] (`19`), [[azur-promilia]] (`8`), [[uma-musume]] (`8`), [[reverse-1999]] (`7`), [[chaotic-plartima]] (`3`), และ [[resonance-solstice]] (`2`).

### เกมคอนโซล / Action / PC (`13` หน้าเกม)
- [[pokemon]] (`56` สตรีม — *Radical Red*, *Champions*, *Legends Z-A*), [[zelda]] (`25` สตรีม — *BotW No-Guide* & *TotK*), [[minecraft]] (`21` สตรีม — Modpack *Cisco's RPG* / *Dragonfyre*), [[gta-6]] (`21` สตรีม — ถึงวันวางขาย & ข่าวหลุด 200GB), [[monster-hunter]] (`19`), [[deadlock]] (`18`), [[fire-emblem]] (`17` — *Three Houses* พร้อมตำนานคดีโดนโกงตลับ), [[phantom-blade-zero]] (`16`), [[re9-marathon-mewgenics]] (`12`), [[sekiro]] (`10`), [[cyberpunk]] (`8`), [[the-sims]] (`4`), และ [[heartopia]] (`3`).

### ประเด็นสังคม การเมือง เศรษฐกิจ โทคุซัทสึ อนิเมะ & สารคดี (`6` Topics)
- [[gacha-business-and-endgame-philosophy]] (`161` สตรีม): ตลาด Red Ocean, กับดักหอ 3 ห้อง, Generative AI / "AI Slop", และปรัชญา MGS3.
- [[anime-manga-cinema]] (`143` สตรีม): [[mappa]] (*Chainsaw Man*), *Bleach TYBW*, *Steel Ball Run*, *One Piece*, และ *Godzilla Minus Zero*.
- [[thai-politics-and-economy]] (`102` สตรีม + ประวัติศาสตร์ [[stream-iyufnybnjze]]): ม็อบ Gen Z, MOU 43/44, กยศ. เทียบประกันสังคมฝรั่งเศส, เลือกตั้ง 2026 (ใช้ safe metaphor Masking ครบถ้วน).
- [[vlogs-hardware-and-personal-life]] (`84` สตรีม): Nintendo Switch 2, MRT/งานหนังสือ/TGS/Comiket, สุขภาพ, และประสบการณ์ชีวิต.
- [[tokusatsu-watch-party]] (`38` สตรีม): Watch Party รายสัปดาห์ *Super Hero Time Thailand* ([[kamen-rider-zeztz]], *My-Th*, *Ultraman Arc/Teo*, Project R.E.D.).
- [[live-mai-lap-documentary]] (`24` สตรีม): สารคดีประวัติศาสตร์ รามายณะ, คดีประวัติศาสตร์ *ท่านอิมู รุ่นที่ 8* (masked), และเคสดังโซเชียล.

---

## 2. แกนวิศวกรรมและเครื่องมือ Python (`wiki/engineering/` — `16` หน้า)
- **สถาปัตยกรรมหลัก**: [[prep-first-full-context-48k]] ([[code-change-prep-first-48k]]) และผลตรวจ [[post-mortem-scrutinize-cqll7dq35bw]].
- **Stage 1–5 Pipeline Scripts**: [[prepare-video-py]], [[update-garbled-dictionary-py]], [[chunk-enrichment-py]], [[chunk-storyboard-prep-py]], [[audio-webcam-cues-py]], [[obs-layout-py]], [[webcam-storyboard-py]], [[chunk-scanner-py]], [[process-chunks-local-py]], [[dynamic-chunk-py]], [[prompts-py]], [[assembly-py]], [[audit-gaps-and-check-sections]].
- **Wiki Automation Scripts**: [[anibon-wiki-tools]] (`wiki_tool.py`, `acquire_streams.py`, `ingest_streams_batch.py`, `stream_taxonomy.py`).
