"""Resource path resolution for anibon-stream-synthesis.

Resolves resource files by walking up from this package until it finds the
``resources/`` directory that actually contains the requested resource. This
works from the repo root (``resources/``), from vendored per-skill copies
(``skills/<skill>/scripts/anibon/``), and after standalone skill extraction.

Consumers use ``resource_path(name)``:
  - clean_garbled_english.py
  - check_sections.py
  - _chunker.py — default_mappings.json
  - detect_signals.py
"""
from pathlib import Path

_FILE = Path(__file__).resolve()


def resource_path(name: str) -> Path:
    """Return an absolute path to resource ``name``.

    Walks up from this module until finding a ``resources/<name>`` that exists,
    falling back to the last candidate if none is found.
    """
    candidates = [p / "resources" / name for p in _FILE.parents]
    first = next((p for p in candidates if p.is_file()), None)
    return first or candidates[0]


def plugin_root() -> Path:
    """Return absolute path to the anibon-stream-synthesis plugin root."""
    marker = _FILE.parent / "resources"
    for p in _FILE.parents:
        if (p / "resources").is_dir():
            return p
    return _FILE.parent


def load_default_mappings() -> dict:
    """Load default transcript correction mappings from resources."""
    import json
    return json.loads(resource_path("default_mappings.json").read_text(encoding="utf-8"))
