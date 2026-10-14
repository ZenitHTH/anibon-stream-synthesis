import sys
from pathlib import Path

_TEST_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _TEST_DIR.parent
_PLUGIN_ROOT = _SKILL_DIR.parent.parent

for _p in [_SKILL_DIR / "scripts", _PLUGIN_ROOT / "lib"]:
    _p_str = str(_p)
    if _p_str not in sys.path:
        sys.path.insert(0, _p_str)
