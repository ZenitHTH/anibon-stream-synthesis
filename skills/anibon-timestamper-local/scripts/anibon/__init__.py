import pkgutil
import sys
from pathlib import Path

_LIB_DIR = str(Path(__file__).resolve().parents[4] / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

__path__ = pkgutil.extend_path(__path__, __name__)
