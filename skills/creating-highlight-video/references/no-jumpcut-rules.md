---
name: highlight-no-jumpcut-rules
description: Use when selecting timestamps for a highlight reel from a livestream or talk-show, to ensure no jarring jump cuts appear and the narrative flows smoothly between scenes.
---

# Highlight No-Jump-Cut Rules

## Overview

A professional checklist and ruleset for selecting and sequencing highlight scenes from a long-form stream, ensuring zero unintentional jump cuts. Based on Walter Murch's **Rule of Six** (film editing priority hierarchy) and broadcast talk-show clip-selection standards.

---

## Core Philosophy: Invisible Editing

> "If the viewer is noticing the cuts, the editing has failed." — Walter Murch

A highlight reel should feel like a **single coherent story**, not a collection of disconnected clips. Every cut must be earned. Every skipped section must be justified.

---

## Walter Murch's Rule of Six (Priority Order)

When choosing where to cut, rank your decisions by this hierarchy. If you must break a rule, always break the **lowest-ranked** one first:

| Priority | Factor | Weight | Question to Ask |
|----------|--------|--------|-----------------|
| 1 | **Emotion** | 51% | Does this cut preserve the emotional build-up? |
| 2 | **Story** | 23% | Does this cut advance the narrative meaningfully? |
| 3 | **Rhythm** | 10% | Does this cut happen at a natural pause or beat? |
| 4 | **Eye Trace** | 7% | Does the visual focus flow naturally into the next shot? |
| 5 | **2D Plane** | 5% | Does the composition feel consistent? |
| 6 | **3D Space** | 4% | Does spatial orientation remain clear? |

For **talk-show and livestream** content, #1 (Emotion) and #2 (Story) dominate everything. Never sacrifice them for a shorter or "cleaner" clip.

---

## The 5 Iron Rules for No-Jump-Cut Highlights

### Rule 1: No Cold Start — Always Give Context First

Every segment MUST open with at least **30–60 seconds of setup** before the emotional peak.

- **DO:** Include the moment Boat says "So the news this week is…" before the actual announcement.
- **DON'T:** Start mid-sentence, dropping the viewer into a climax without any setup.

**Why:** A cold start (dropping into a punchline without the premise) is the #1 cause of viewer confusion. The brain needs an "establishing shot" of the topic before the payoff lands.

---

### Rule 2: The But/Therefore Connector Test

Before accepting any scene transition, apply this test verbally:

> "We just saw [Scene A], **therefore** we now watch [Scene B]."
> OR: "We just saw [Scene A], **but** [Scene B] happened."

If the connector is **"and then"** — the transition is a jump cut. **STOP** and either:
1. Include a bridging scene between A and B, OR
2. Merge A and B into one continuous scene.

---

### Rule 3: The 5-Minute Context Buffer Rule

For any scene selected from **more than 15 minutes** after the previous scene, you MUST include a minimum **5-minute buffer window** ending at the new scene's start.

```
Selected Scene Start:   [HH:MM:SS]
Buffer Window STARTS:   [HH:MM:SS minus 5 min]
```

This buffer prevents the "teleport cut" — where the viewer is suddenly in a completely new topic with no transition.

**Exception:** No buffer needed if the streamer gives a verbal transition. Examples of valid verbal bridges:
- "OK, moving on to the next news item…"
- "Chat, let me show you something else…"
- "Speaking of that, here's X…"

---

### Rule 4: Merge Contiguous Scenes — Never Split Flow

If two selected scenes are within **2 minutes** of each other in the source stream, they **MUST** be merged into one continuous timestamp range.

- BAD: `[01:15:00 - 01:20:00]` and `[01:21:30 - 01:25:00]` (gap of 1.5 min → jump cut)
- GOOD: `[01:15:00 - 01:25:00]` (merged; the 1.5-min gap is a natural breath, not dead content)

---

### Rule 5: The Pacing Rollercoaster — Alternate High/Low Energy

Do NOT string multiple high-energy peaks back to back. Structure the reel like a heartbeat:

```
HIGH → BREATH → HIGH → BREATH
```

- **HIGH Energy:** Reaction, debate, announcement, punchline
- **BREATH Moment:** Chat reading, casual explanation, light humor, topic transition

Stringing peaks without breathing room creates "fatigue cuts" — the viewer becomes numb to the excitement.

---

## Scene Transition Decision Tree

```
Is the gap between scenes < 2 minutes?
├── YES → MERGE into one range (Rule 4)
└── NO
    └── Does the streamer verbally transition between topics?
        ├── YES → Safe to cut. Note the verbal bridge timestamp.
        └── NO
            └── Is the new scene a completely different topic?
                ├── YES → Add 5-min buffer window before new scene (Rule 3)
                └── NO (same topic, continuation)
                    └── Apply But/Therefore test (Rule 2)
                        ├── PASSES → Safe to cut
                        └── FAILS (And Then) → Add bridging content
```

---

## Output Recipe for Highlight Selection Files

Every scene in `highlight_selection.md` MUST have all five fields:

```
`[HH:MM:SS - HH:MM:SS]` - **[Scene Title]**
*Emotion beat:* [e.g., "High excitement — major reveal", "Comedic relief — Boat reacts"]
*Why selected (But/Therefore):* [Connect to previous scene with "but" or "therefore"]
*Why gap was skipped:* [What happened in the skipped section and why it is safe to cut]
*Buffer included:* [YES — opens with 60s setup | NO — verbal bridge at HH:MM:SS | N/A — first scene]
*Energy level:* [HIGH | MEDIUM | LOW]
```

---

## Red Flags — STOP and Re-evaluate

- **Cold Start:** Clip opens mid-sentence with no topic context.
- **And Then Jump:** Cannot connect scenes with "but" or "therefore" — only "and then".
- **Consecutive Peaks:** Three or more HIGH-energy segments in a row with no MEDIUM/LOW breath.
- **Unexplained Gap > 15 min:** No verbal bridge and no buffer window included.
- **Split Contiguous Content:** Two scenes within 2 minutes of each other not merged.

---

## Common Mistakes

| Mistake | Why It Happens | Fix |
|---------|---------------|-----|
| Starting at the punchline | Desire for short, punchy clip | Add 30–60s of setup. Emotion needs buildup. |
| Cutting during a laugh | Seems like a natural break | Laughs are peaks. Cut AFTER the reaction settles. |
| Topic-hopping without bridges | "Dead air" feels wasteful | Preserve the streamer's own topic transitions — they are the bridge. |
| Fear of long videos | Trying to hit an arbitrary short runtime | Length does not equal quality. Flow beats brevity. |
| Removing all low-energy moments | "Only keep the good parts" | Low-energy breaths make high-energy peaks feel earned. |

---

## Final Self-Check Before Submitting Selection

Answer YES to all before writing `highlight_selection.md`:

- [ ] Every scene connects to its neighbors via "but" or "therefore"?
- [ ] Every gap > 15 min has a verbal bridge OR a 5-min buffer?
- [ ] No two scenes within 2 minutes of each other left unsplit?
- [ ] Energy pattern alternates — not all peaks, not all calm?
- [ ] Every scene opens with at least 30s of contextual setup?
- [ ] All five output recipe fields filled in for every selected scene?
