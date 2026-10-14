import sys
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parent.parent
_PLUGIN_ROOT = _SKILL_DIR.parent.parent
for _p in (_SKILL_DIR / "scripts", _PLUGIN_ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
