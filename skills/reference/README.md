# Reference Knowledge Base Index

This directory contains external reference knowledge databases and game lore files used by nibon-stream-synthesis skills to verify character names, game titles, and card terms during transcript analysis.

## Directory Structure

- FGO and DATA/ — Fate/Grand Order servant database (tlas_fgo.db), noble phantasm names, and story chapter chronologies.
- Yu-Gi-Oh DATA/ — Yu-Gi-Oh card database (ygo_cards.db), archetypes, and tournament terminology.

## Signal Matching & Subagent Ingestion

1. **Signal Detection**: scripts/detect_signals.py matches transcript TF-IDF terms against 
esources/signal_config.json and knowledge.json.
2. **Database Verification**: nibon-world-identity queries tlas_fgo.db or ygo_cards.db to map Thai phonetic Whisper outputs to canonical English/Japanese character names.
3. **Subagent Prompt Injection**: scripts/subagent-prompt-builder.py injects matched reference markdown/database data into subagent prompts before chunk processing.
