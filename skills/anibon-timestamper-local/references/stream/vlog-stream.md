---
name: anibon-vlog-stream
description: Use when processing a live stream or video chunk featuring outdoor vlogs, IRL events, convention walkthroughs (Nippon Haku, Japan Expo, Comic World), food tasting, booth showcases, fan meetups, or worksite streams.
---

# Anibon Vlog & IRL Event Stream

## Overview
This reference guides topic breakdown, dual-synthesis timestamping, and tag classification for outdoor vlogs, IRL conventions/exhibitions, food tours, and worksite streams by PhuBoat (Anibon Official).

## When to Use
- Directed here by `anibon-timestamper` orchestrator when signals detect `vlog`, `nippon haku`, `japan expo`, `comic world`, `งานอีเวนท์`, `งานหนังสือ`, `พาเที่ยว`, `งานญี่ปุ่น`, `วล็อก`.
- Stream video is recorded on-location, walking through an event hall, tasting food, meeting fans, or visiting booths.

## Behaviors & Rules

### 1. IRL Convention & Exhibition Breakdown Pattern
When Boat streams long walkthroughs (e.g. 2–5 hours at NIPPON HAKU, Comic World, Japan Expo):

**Breakdown into 10–20 minute logical milestones**:
1. `[Greeting]` / `[Tour]` **Arrival & Entry**: Arriving at the venue (e.g. Paragon Hall, Queen Sirikit Center, BITEC), stream greeting, ticket/badge check, first impressions.
2. `[Booth]` / `[Merch]` **Zone & Booth Exploration**: Visiting specific anime, manga, gaming, travel, or education booths (Kadokawa, Good Smile Company, Animate, Bushiroad, Dex, Phoenix Next).
3. `[Food]` **Food & Sweets Tasting**: Ordering and tasting authentic Japanese dishes/snacks (Takoyaki, Yakisoba, Ramen, Wagyu, Matcha, Ichigo Daifuku, Melon Soda).
4. `[Stage]` **Stage Shows & Performances**: Live concerts, idol stages, cover dance, anime song performances, or guest talk shows.
5. `[Cosplay]` **Cosplayer Encounters & Showcase**: Admiring cosplay craftsmanship, posing, or chatting with cosplayers.
6. `[Interview]` / `[FanMeet]` **Fan Meetups & Staff Interviews**: Interacting with viewers IRL, signing autographs, taking photos, or interviewing booth staff.
7. `[Talk]` / `[Vlog]` **Walking Banter & Industry Tangents**: Spoken commentary and jokes while navigating between halls.

---

### 1.5 Book Fair & Shopping Challenge Breakdown Pattern
When Boat streams book fair walkthroughs (สัปดาห์หนังสือแห่งชาติ, มหกรรมหนังสือแห่งชาติ, Comic Avenue):

**Breakdown into 10–20 minute logical milestones**:
1. `[Greeting]` / `[Tour]` **Hall Arrival & Challenge Setup**: Arriving at Queen Sirikit Center (QSNCC), introducing friends, stating budget limits (e.g. 1,000 THB budget challenge) or shopping targets.
2. `[Booth]` / `[Merch]` **Publisher Booth Shopping**: Browsing specific publishers (Phoenix Next, First Page Pro, Siam Inter, Luckpim, Dexpress, Kinokuniya, Salmon Books).
3. `[Merch]` **Special Edition & Boxset Hunting**: Inspecting limited edition boxsets, acrylic standees, artbooks, and exclusive postcards.
4. `[Talk]` / `[Merch]` **Tsundoku Banter ("ซื้อมาดอง")**: Comedic commentary on buying stacks of unread manga/novels with friends.
5. `[Booth]` / `[Gameplay]` **Tabletop & Board Game Area**: Checking out Warhammer 40K miniatures or card game tables in the book fair hall.
6. `[Food]` / `[Break]` **Food & Rest Break**: Taking a break at food stalls or beverage booths inside the convention center.
7. `[FanMeet]` **Viewer Greetings**: Meeting ANIBON stream community members and exchanging greetings.
8. `[Tour]` / `[Vlog]` **Shopping Haul Review & Wrap-up**: Reviewing purchased books, calculating total spend against the budget, and saying goodbye.

---

### 2. Worksite / Hands-on Vlog Breakdown Pattern
When Boat streams construction/pipeline/workshop tasks:
1. `[Work]` **Task Start & Tool Setup**: Explaining task, materials, safety gear, tool calibration.
2. `[Work]` **Process & Technique**: Demonstrating welding, cutting, fitting, measuring.
3. `[Talk]` **Spoken Story / Tangent**: Hands-free monologues, personal anecdotes, or industry stories during manual work.
4. `[Chat]` / `[Donation]` **Viewer Interaction**: Answering tool questions or chatting with stream.
5. `[Work]` **Inspection & Milestone**: Showing completed weld/cut/assembly.

---

### 3. Dual-Synthesis for VLOGs (Visual Location + Spoken Audio)
- **Visual Grounding**: The camera points at physical objects (signs, booth banners, menu boards, stage backdrops, cosplayers). Read the exact booth name and food item from the camera view.
- **Spoken Grounding**: Boat may discuss anime production economics or FGO while walking past a food booth. Combine both:
  - Example: `[Booth] เดินชมบูธ Good Smile Company พร้อมคุยเรื่องสเกลฟิกเกอร์ FGO`
  - Example: `[Food] ชิมทาโกยากิร้อนๆ ในโซนอาหาร พร้อมรีวิวรสชาติต้นตำรับ`

---

### 4. Tag Taxonomy for VLOGs

| Tag | Usage | Example |
| :--- | :--- | :--- |
| `[Tour]` / `[Vlog]` | General event walkthrough, hall transitions | `[Tour] เดินเก็บบรรยากาศเปิดงาน NIPPON HAKU 2026` |
| `[Booth]` | Visiting a specific company/creator booth | `[Booth] แวะชมบูธ Kadokawa ดูมังงะและไลท์โนเวลใหม่` |
| `[Food]` | Food orders, eating, tasting, beverage review | `[Food] ชิมมัตฉะพรีเมียมและไดฟูกุสตรอว์เบอร์รีสด` |
| `[Stage]` | Live performance, music, cover dance, talk show | `[Stage] ชมการแสดง Cover Dance บนเวที Main Stage` |
| `[Cosplay]` | Cosplayers, costume showcase, photography | `[Cosplay] ทักทายเลเยอร์คอสเพลย์ตัวละคร FGO ในงาน` |
| `[FanMeet]` | Meeting stream viewers, autographs, photos | `[FanMeet] ถ่ายรูปและพูดคุยกับแฟนคลับ ANIBON ที่เข้ามาทัก` |
| `[Interview]` | Direct interview with staff, creator, or guest | `[Interview] สัมภาษณ์ทีมงานบูธเรียนต่อประเทศญี่ปุ่น` |
| `[Merch]` | Shopping, inspecting figures, acrylic stands | `[Merch] ช้อปปิ้งสแตนดี้และกู๊ดส์อนิเมะลิขสิทธิ์แท้` |
| `[Work]` | Manual pipeline/construction/site tasks | `[Work] สาธิตเทคนิคการเชื่อมท่อเหล็กหน้างาน` |

---

### 5. Environmental Audio & Crowd Handling
- Event halls have loud ambient music, announcement PAs, and chatter.
- Subagents must not mistake background PA announcements or background song lyrics for the streamer's spoken topic. Focus on PhuBoat's microphone channel and camera direction.
