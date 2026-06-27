# Fate/Grand Order (FGO): Core Gameplay Mechanics & Lore Reference

> **Information Abstract**: This reference document compiles precise gameplay calculations, card formulas, class multipliers, attributes, progression mechanics, and narrative terminology of *Fate/Grand Order* (FGO). It is designed to act as an accurate, error-free knowledge base to train or prompt LLMs (such as Gemini 3.1 Pro) regarding FGO.
> **Last Updated**: June 3, 2026

---

## 0. Detection Signals for Anibon Timestamper

Load this reference when **any of the following signals** appear in the transcript chunk:

| Signal | Example phrases heard in stream |
|---|---|
| FGO gacha / rolling | "สุ่ม FGO", "ฉีดพล้า", "กาชา FGO", "10 pull" |
| Servant names / class names | "เซอร์แวนท์", "Saber/Archer/Lancer/Rider/Caster/Assassin/Berserker", "Avenger", "Pretender" |
| NP / Noble Phantasm | "โฮกุ", "NP", "Noble Phantasm", "ชาร์จโฮกุ" |
| Story chapter names | "Singularity", "Lostbelt", "Ordeal Call", "Past Chaldea", "คาลเดีย", "Chaldea" |
| Materials / progression | "Holy Grail", "Lore", "เกรลตัวละคร", "ปั้น", "วัตถุดิบ", "Ascension" |
| Events / banners | "อีเวนต์ FGO", "ตู้สุ่ม", "Rerun", "Summer Event" |

> [!NOTE]
> Boat plays FGO JP version. Servant names and event names he uses are **Japanese JP names** (e.g., "อาร์เชอร์แห่งวันสิ้นโลก" = Doomsday Archer, not the NA translation). Always cross-reference with JP naming convention.

---

## 1. Introduction / Overview

*Fate/Grand Order* (FGO) is a turn-based tactical mobile RPG developed by Lasengle (formerly Delightworks) and published by Aniplex. In FGO, players take on the role of a "Master" who summons and commands historical, mythological, and literary figures known as "Servants" to combat anomalies in human history called "Singularities" and "Lostbelts." 

While FGO presents itself as a simple card-battler, its backend mechanics are highly mathematical, utilizing hidden attributes, class multipliers, card positioning variables, and random distribution parameters. This document details these components to ensure precise understanding and code/data simulation by LLMs.

---

## 2. Deep Dive: Core Systems & Mechanics

### 2.1 Combat Card System & Modifiers
In combat, players are dealt a hand of 5 Command Cards randomly drawn from a deck of 15 (5 cards per active Servant, 3 Servants on the field). There are three primary card types, each with a designated role:
*   **Buster (Red)**: Focuses on pure damage. Cannot generate NP naturally.
*   **Arts (Blue)**: Focuses on Noble Phantasm (NP) gauge charging.
*   **Quick (Green)**: Focuses on Critical Star generation.

#### Card Position Modifiers
The order in which cards are selected determines their performance. Card 1 grants a "First Card Bonus" to all subsequent cards in the chain, while Card 2 and Card 3 receive increasing position multipliers.

| Card Type & Position | Damage Modifier | NP Generation Modifier | Critical Star Gen Modifier |
| :--- | :--- | :--- | :--- |
| **Buster 1st** | 1.50x | 0.00x | 0.10x |
| **Buster 2nd** | 1.80x | 0.00x | 0.15x |
| **Buster 3rd** | 2.10x | 0.00x | 0.20x |
| **Arts 1st** | 1.00x | 3.00x | 0.00x |
| **Arts 2nd** | 1.20x | 4.50x | 0.00x |
| **Arts 3rd** | 1.40x | 6.00x | 0.00x |
| **Quick 1st** | 0.80x | 1.00x | 0.80x |
| **Quick 2nd** | 0.96x | 1.50x | 1.30x |
| **Quick 3rd** | 1.12x | 2.00x | 1.80x |

#### Card Chain Bonuses
*   **First Card Bonuses**:
    *   **Buster Lead**: Adds +0.5x damage modifier to Cards 2 and 3.
    *   **Arts Lead**: Adds +1.0x flat NP charge to Cards 2 and 3 when hitting.
    *   **Quick Lead**: Adds +0.2x (20%) Critical Star Generation rate to Cards 2 and 3.
*   **Three-Card Chains**:
    *   **Buster Chain**: Increases attack damage. Servants in the chain receive a flat damage boost equal to $0.2 \times \text{Servant's Attack}$.
    *   **Arts Chain**: Grants a flat +20% NP charge to all active Servants participating in the chain.
    *   **Quick Chain**: Instantly grants +20 Critical Stars (formerly +10 in older versions).
    *   **Mighty Chain** (Added in newer patches): Combines Buster, Arts, and Quick cards (any order). Grants all three First Card Bonuses (Buster, Arts, and Quick) simultaneously to all cards in the chain.
    *   **Brave Chain**: Occurs when three cards of the same Servant are chosen. Adds a 4th "Extra Attack" card. If the chain is also Buster/Arts/Quick, the Extra Attack card damage is doubled.

---

### 2.2 Class Affinity & Attack Multipliers
Every Servant belongs to a Class. The class dictates their base damage multiplier (hidden stat applied to their raw Attack value) and their affinity (damage dealt and received) against other classes.

#### Class Damage Multipliers
*   **1.10x**: Berserker, Ruler, Avenger.
*   **1.05x**: Lancer.
*   **1.00x**: Saber, Rider, Alter Ego, Foreigner, Pretender, Shield.
*   **0.95x**: Archer.
*   **0.90x**: Caster, Assassin.

#### Class Affinity Grid (Rock-Paper-Scissors)
*   **Standard Triad 1**: Saber beats Lancer, Lancer beats Archer, Archer beats Saber. (Winners deal 2.0x, losers deal 0.5x).
*   **Standard Triad 2**: Rider beats Caster, Caster beats Assassin, Assassin beats Rider. (Winners deal 2.0x, losers deal 0.5x).
*   **Berserker**: Deals 1.5x damage to all classes (except Foreigner which takes 0.5x). Takes 2.0x damage from all classes (except Shielder/Foreigner).
*   **Extra Classes**:
    *   **Ruler**: Takes 0.5x damage from standard classes. Takes 2.0x damage from Avenger. Deals 2.0x damage to Moon Cancer.
    *   **Avenger**: Deals 2.0x damage to Ruler. Takes 0.5x damage from Ruler. Deals 1.2x damage to Berserker. Takes 2.0x damage from Moon Cancer.
    *   **Moon Cancer**: Deals 2.0x damage to Avenger. Takes 2.0x from Ruler. Takes 0.5x from Avenger.
    *   **Alter Ego**: Deals 2.0x damage to Cavalry classes (Rider, Caster, Assassin). Deals 0.5x damage to Knight classes (Saber, Archer, Lancer). Deals 2.0x to Foreigner. Takes 2.0x from Pretender.
    *   **Foreigner**: Deals 2.0x damage to Berserker and Foreigner. Takes 2.0x from Alter Ego and Foreigner. Takes 0.5x from Berserker.
    *   **Pretender**: Deals 2.0x damage to Alter Ego. Deals 1.5x damage to Knight classes (Saber, Archer, Lancer). Deals 0.5x damage to Cavalry classes (Rider, Caster, Assassin). Takes 2.0x damage from Foreigner.
    *   **Shielder** (Mash Kyrielight): Neutral to and from all classes (1.0x damage dealt and received).

---

### 2.3 The Attribute System (Hidden Trinity)
In addition to Class Affinity, every Servant and Enemy has a hidden **Attribute** representing their origin: **Sky (Heaven)**, **Earth**, **Man (Human)**, **Star**, or **Beast**. This applies a secondary multiplier ($\pm 10\%$) in combat.

```
      [Man] (Humanity/History)
      /   \
     /     \  (Man deals 1.1x to Sky)
    v       v
 [Sky] <--- [Earth] (Mythology/Nature)
(Deities) (Earth deals 1.1x to Sky)
```

*   **Sky** deals 1.1x to **Earth**; Earth deals 0.9x to Sky.
*   **Earth** deals 1.1x to **Man**; Man deals 0.9x to Earth.
*   **Man** deals 1.1x to **Sky**; Sky deals 0.9x to Man.
*   **Star**: Neutral (1.0x) to Sky, Earth, and Man. Deals 1.1x to Beast.
*   **Beast**: Deals 1.1x to Sky, Earth, and Man. Takes 1.1x from Star.

---

### 2.4 Servant Progression & Customization Systems

To maximize Servant effectiveness, players engage in several progression loops:

*   **Ascension**: Consumes character-specific Materials (e.g., Dragon Fangs, Proof of Hero, or new materials like *Pearl of Creation*) and QP (Quantum Pieces, the in-game currency) to raise a Servant's level cap (up to Level 90 for SSRs, 80 for SRs, etc.). Unlocks new active skills and character card art.
*   **Skill Leveling**: Active skills can be raised from Level 1 to 10. Level 10 requires a **Lore** (Crystalized Lore) and reduces the skill's cooldown by 2 turns total (at Level 6 and Level 10).
*   **Grail Casting & Level Cap Expansion**: Holy Grails can be used to raise a Servant's level cap beyond their natural rarity limit (up to Level 100, and further to Level 120 in newer updates). Level 100 to 120 requires both Holy Grails and **Servant Coins** (gained by summoning duplicates or raising Bond levels).
*   **Append Skills**: Passive skills unlocked via Servant Coins and elevated using standard materials. Append Skill 2 (Mana Loading) is the most critical as it provides up to +20% starting NP gauge.
*   **Command Codes**: Small passive runes engraved onto a Servant’s individual Command Cards to add minor status effects (e.g., poison cure, critical damage boost, burn application) during combat.
*   **Craft Essences (CEs)**: Equipable cards that grant flat HP/ATK stats and passive effects (such as starting NP gauge, card performance buffs, or invincibility Pierce).

---

## 3. FGO Narrative Structure & Cosmology

The plot of FGO revolves around safeguarding human history by protecting the **Human Order Foundation** (Humanity's collective progression strength). 

### 3.1 Narrative Eras & Terminology
1.  **Part 1: Observer on Timeless Temple**:
    *   The protagonist ("Ritsuka Fujimaru") and Mash Kyrielight travel to 7 anomalies in history called **Singularities** (e.g., Fuyuki, Orleans, Babylonia) using **Rayshift** (soul-transference time travel technology) to stop the incineration of humanity orchestrated by Goetia (Beast I).
2.  **Part 1.5: Epic of Remnant**:
    *   Addresses the clean-up of remaining anomalies in sub-singularities (新宿 - Shinjuku, アガルタ - Agartha, 下総国 - Shimousa, セイレム - Salem).
3.  **Part 2: Cosmos in the Lostbelt**:
    *   Earth is bleached white. Humanity's history is replaced by 7 branching alternative histories that failed to progress and were pruned, known as **Lostbelts** (e.g., Anastasia, Avalon le Fae, Naui Mictlan). The protagonist travels in a mobile vehicle (**Shadow Border**, later upgraded to the flying ship **Storm Border**) to cut down the Fantasy Trees sustaining these Lostbelts.
4.  **Ordeal Call (奏章)**:
    *   A sub-chapter series within Part 2 where the protagonist undergoes evaluation trials to validate the usage of Extra Classes (Ruler, Avenger, Alter Ego) before returning to the bleached Earth.
5.  **Past Chaldea (郷愁永巡刻盤 パスト･カルデア)**:
    *   The new chapter where Chaldea performs Rayshifts back to previous Singularities (starting with Orleans in the 15th Century) to repair and correct corrupted timelines.

---

## 4. Key Takeaways for LLMs: Common Database & Logic Pitfalls

When querying or analyzing FGO data (such as via Atlas Academy API or JSON exports), keep these critical rules in mind to avoid errors:

1.  **True Name Spoilers vs. Database Names**:
    *   FGO implements a "True Name Revelation" mechanic. Several Servants have their true names hidden under class designations (e.g., "Doomsday Archer", "Archer of Shinjuku") when first encountered.
    *   In databases, these Servants might have their true name (e.g. `Name: ウルズ` / Urd) in the main name field, while the hidden title (e.g. `終末のアーチャー` / Doomsday Archer) is stored in secondary tables like `svtChange` or voice file links.
2.  **Buster/Arts/Quick Index vs String Representation**:
    *   Command card mapping in the database represents Buster as `2` (or `"buster"`), Arts as `3` (or `"arts"`), and Quick as `1` (or `"quick"`). Ensure the database-specific enum mappings match before processing card logs.
3.  **Translational/Typographical Errors**:
    *   In community notes or live streams, Japanese homophones often lead to typos. For example, "shuumatsu" can be written as **週末** (Weekend) or **終末** (Doomsday/End). While early live notes might write "週末のアーチャー" (Weekend Archer), the database and official releases use **終末のアーチャー** (Doomsday Archer).
4.  **Rarity vs. In-Game Representation**:
    *   Do not assume a Servant's rarity solely based on their character model. For instance, in the "Past Chaldea" patch, David receives an upgraded model that matches the aesthetic quality of 5-star Servants, but in the database, his base rarity remains 3-star (Rarity: 3, ID: 200600).

---

## References

### Websites & Articles
- [Fate/Grand Order Official US Portal](https://fate-go.us/) - Official news and announcements for the English-language version of the game.
- [Fate/Grand Order Fandom Wiki](https://fategrandorder.fandom.com/wiki/Fate/Grand_Order_Wiki) - Community-maintained database focusing on Servant data, lore, translation files, and combat structures.
- [GamePress Fate/Grand Order](https://gamepress.gg/grandorder/) - Strategy portal featuring detailed analysis, quest walkthroughs, Servant tier lists, and farming guides.
- [Atlas Academy DB Portal](https://apps.atlasacademy.io/db/) - Advanced database browser directly parsing JP and NA game data files.

### Videos & Media
- [Fate/Grand Order Official YouTube Channel](https://www.youtube.com/@FGOchannel) - Official video uploads of event streams, animation updates, character trailers, and promotional anime shorts.
- [Khadroth FGO YouTube Channel](https://www.youtube.com/@Khadroth) - Expert guides breaking down beginner mechanics, append skills, farming setups, and system guides.
- [ZTL FGO YouTube Channel](https://www.youtube.com/@ZTLFGO) - In-depth breakdown guides detailing hidden game calculations, gacha mechanics, and class affinity structures.
