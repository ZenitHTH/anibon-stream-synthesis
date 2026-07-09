---
name: livestream-scene-selection
description: Use when selecting, filtering, or marking timelines from a livestream to create a summary, highlight reel, or send instructions to a video editor
---

# Livestream Scene Selection

## Overview
A framework for selecting and documenting scenes from long-form livestreams. It ensures the resulting summary maintains narrative flow, avoids confusing jump cuts, and provides clear instructions to video editors based on "But / Therefore" storytelling.

## When to Use
- When extracting highlights from a long livestream. Do not worry about the final length. Condensing an 11-hour stream into a 6-hour summary is still a summary because it saves 5 hours of time! Focus on the storyline first.
- When writing a timeline, script, or scene-selection list for a video editor.
- When filtering timestamps to build a cohesive narrative from gameplay.

**REQUIRED COMPANION SKILL:** Before finalizing any scene selection, run `highlight-no-jumpcut-rules` to validate all transitions. It enforces Walter Murch's Rule of Six, the 5-min buffer rule, the pacing rollercoaster, and the merge-contiguous rule.

## Core Principles: Good vs. Bad Storytelling

### The "But / Therefore" Rule (Good)
Every selected scene MUST connect to the previous one with "but" or "therefore".
- **Setup:** The player enters the gym.
- **Therefore:** The player fights the gym leader.
- **But:** The player loses because their team is under-leveled.
- **Therefore:** The player goes to train.

### The "And Then" Trap (Bad)
Avoid disconnecting scenes with "and then", which causes confusing jump cuts.
- **Bad:** The player fought the gym leader. *And then* they were suddenly in a casino fighting a boss.
- **Fix:** Include the travel, the context, or the decision-making process before the casino fight. Never drop the viewer into the middle of an action sequence without knowing how the player got there.
- **Bad:** The player suddenly uses a powerful new Pokémon or item to win a fight.
- **Fix:** Include the scene where the player catches that key Pokémon or finds that crucial item. Viewers must not be confused about where it came from.

### Establishing the Location
- **Rule:** When the player travels to a new area (like a town, gym, or dungeon), you MUST include the scene where the player first arrives or establishes the location.
- **Why:** Viewers get confused if the scene cuts directly into a fight or building Pokémon without knowing *where* the player is. Show the arrival to ground the scene.

### Merging Contiguous Scenes
- **Rule:** If two selected scenes occur back-to-back or are naturally continuous in time, do NOT cut between them. Merge them into a single continuous block to maintain the natural flow.

### Progression vs. Farming
- **Keep Progression:** Be careful when selecting scenes to ensure they actually show story progression or the finding of important items/Pokemon.
- **Skip Farming:** If a scene is just repetitive farming or grinding with no story importance, skip it. Viewers want to see how the story progresses, not the repetitive grind.

## Output Recipe: Timeline Format

When generating a timeline for a video editor, your output MUST follow this structural recipe for every selected scene:

1. **Timestamp Range:** `[HH:MM:SS - HH:MM:SS]`
2. **Scene Description:** Clear summary of the action.
3. **Selection Rationale (Why Selected):** Explicitly explain *why* this scene is essential to the storyline, how it connects to the previous scene (But/Therefore), and what makes it entertaining.
4. **Omission Rationale (Why Skipped):** Explicitly explain *why* the gap of time between the previous scene and this current scene was skipped (e.g., "Skipped 30 minutes of grinding because no story progression occurred").

**Example:**
`[01:15:30 - 01:20:10]` - **Walking to Rocket Casino & Prep**
*Why selected:* Provides crucial context. We just finished the S.S. Anne, *therefore* we need to show the journey to the casino so the viewer doesn't feel disoriented by a sudden jump cut into a new battle. 
*Why skipped previous section:* Skipped [01:05:00 - 01:15:30] because it was just repetitive grinding and AFK time that adds nothing to the story.

`[01:20:10 - 01:28:45]` - **Rocket Boss Fight (Giovanni)**
*Why selected:* The climax of the current arc. The player prepped their team, *but* Giovanni has a surprise counter. High tension and fun reaction from the streamer.
*Why skipped previous section:* No time skipped, this scene flows immediately from the prep phase.

## Red Flags - STOP and Re-evaluate

- **No Context Jump Cuts:** Did you jump from one location to a completely different one without showing the transition?
- **Missing Rationale:** Did you omit the "Why Selected" or "Why Skipped" note for the editor? They need to know both why a scene is kept and why a chunk of time was cut.
- **Over-cutting:** Is the edit so fast that the viewer misses the emotional buildup? Storyline comes FIRST. Do not worry about video length. If an 11-hour stream becomes a 6-hour summary, it is perfectly fine because you still saved the viewer 5 hours of watching.

## Common Mistakes

| Mistake | Reality / Fix |
|---------|---------------|
| Skipping the "walk-up" or preparation | Viewers get confused by sudden setting changes. Always include 1-2 minutes of setup before a major event. |
| Sudden Location Changes | Viewers don't know where the player is. Always show the arrival or establishing shot of a new town/dungeon before showing fights or preparations inside it. |
| Unexplained Items or Pokémon | Viewers get confused if a new item/Pokémon suddenly appears in a boss fight. Show the moment it was acquired. |
| Making it "too short" | Don't sacrifice the storyline just to hit an arbitrary low duration. Focus on the storyline first! Even a 6-hour summary of an 11-hour stream is a valid summary because it cuts out 5 hours of dead space. |
| Forgetting the "Why" | The video editor needs to know the emotional beat (e.g., "Climax", "Funny frustration") for pacing, and needs to know *why* a section was skipped to ensure no important context was accidentally cut. |
| Cutting Contiguous Scenes | If two selected scenes happen back-to-back, merge them into one timestamp range. Don't make unnecessary cuts. |
| Including Grinding/Farming | Viewers want story progression. Skip repetitive farming segments that don't advance the plot. |
