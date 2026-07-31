"""Resource path resolution for anibon-stream-synthesis.

Consumers (before extraction):
  clean_garbled_english.py:27  — _RESOURCES_DIR = _SCRIPT_DIR.parent / "resources"
  check_sections.py:6          — _RESOURCES_DIR = _SCRIPT_DIR.parent / "resources"
  _chunker.py:50-51            — plugin_root / "resources" / "default_mappings.json"
  detect_signals.py:43         — _RESOURCES_DIR = _SCRIPT_DIR.parent / "resources"
"""
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent  # lib/anibon/ → plugin root


def resource_path(name: str) -> Path:
    """Return absolute path to a resource file under ``resources/``.

    Example: resource_path("garbled_replacements.json")
             → .../anibon-stream-synthesis/resources/garbled_replacements.json
    """
    return _PLUGIN_ROOT / "resources" / name


def plugin_root() -> Path:
    """Return absolute path to the anibon-stream-synthesis plugin root."""
    return _PLUGIN_ROOT


def load_default_mappings() -> dict:
    """Load default transcript correction mappings from resources."""
    import json
    return json.loads((_PLUGIN_ROOT / "resources" / "default_mappings.json").read_text(encoding="utf-8"))
