"""Zero-dependency JSON configuration loader and management for anibon-timestamper-local."""
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Locate skill-level default config.json (skills/anibon-timestamper-local/config.json)
SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_CONFIG_PATH = SKILL_ROOT / "config.json"
SKILL_DOTENV_PATH = SKILL_ROOT / ".env"

_CONFIG: Dict[str, Any] = {}


def _get_val(key: str, default: Any = None) -> Any:
    """Retrieve configuration value prioritizing os.environ over _CONFIG dictionary."""
    env_key = f"ANIBON_{key.upper()}"
    if env_key in os.environ and os.environ[env_key] != "":
        return os.environ[env_key]
    if key in os.environ and os.environ[key] != "":
        return os.environ[key]

    if key in _CONFIG:
        return _CONFIG[key]
    if key.lower() in _CONFIG:
        return _CONFIG[key.lower()]
    if env_key in _CONFIG:
        return _CONFIG[env_key]

    return default


def cfg_str(key: str, default: str) -> str:
    """Retrieve string configuration value or return default."""
    val = _get_val(key, default)
    if val is None or val == "":
        return default
    return str(val)


def cfg_int(key: str, default: int) -> int:
    """Retrieve integer configuration value or return default on error/empty."""
    val = _get_val(key, default)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def cfg_float(key: str, default: float) -> float:
    """Retrieve float configuration value or return default on error/empty."""
    val = _get_val(key, default)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# Aliases for backward compatibility
env_str = cfg_str
env_int = cfg_int
env_float = cfg_float


def load_config(path: Optional[Path] = None, override: bool = False) -> Dict[str, Any]:
    """Load config.json file into in-memory _CONFIG dictionary.

    If path is omitted, loads SKILL_CONFIG_PATH if it exists.
    If override is True, replaces existing keys in _CONFIG and reloads constants.
    """
    global _CONFIG
    cfg_path = Path(path) if path else SKILL_CONFIG_PATH
    if not cfg_path or not cfg_path.is_file():
        return {}

    try:
        content = cfg_path.read_text(encoding="utf-8")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            print(f"[config] Warning: {cfg_path} root is not a JSON object", file=sys.stderr)
            return {}

        if override:
            _CONFIG = parsed.copy()
            reload_config()
        else:
            for k, v in parsed.items():
                if k not in _CONFIG:
                    _CONFIG[k] = v
            reload_config()

        return parsed
    except Exception as e:
        print(f"[config] Warning: Failed to read {cfg_path}: {e}", file=sys.stderr)
        return {}


def load_dotenv(path: Optional[Path] = None, override: bool = False) -> Dict[str, Any]:
    """Backward-compatible loader supporting both config.json and legacy .env files."""
    env_path = Path(path) if path else SKILL_CONFIG_PATH
    if not env_path or not env_path.is_file():
        env_path = SKILL_DOTENV_PATH
        if not env_path or not env_path.is_file():
            return {}

    if env_path.suffix.lower() == ".json":
        return load_config(env_path, override=override)

    try:
        content = env_path.read_text(encoding="utf-8")
        data: Dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                continue
            k, raw_val = line.split("=", 1)
            k = k.strip()
            v = raw_val.strip()
            if v.startswith('"'):
                m = re.match(r'^"([^"]*)"', v)
                if m:
                    v = m.group(1)
            elif v.startswith("'"):
                m = re.match(r"^'([^']*)'", v)
                if m:
                    v = m.group(1)
            elif " #" in v:
                v = v.split(" #", 1)[0].strip()
            data[k] = v
            if override or k not in os.environ:
                os.environ[k] = v

        if override:
            reload_config()
        return data
    except Exception as e:
        print(f"[config] Warning: Failed to parse legacy .env {env_path}: {e}", file=sys.stderr)
        return {}


# ── Configuration Constants ──────────────────────────────────────────────────
PRIMARY_HOST: str = "100.115.25.30"
DEFAULT_PORT: int = 1234
DEFAULT_CHAT_PATH: str = "/v1/chat/completions"
DEFAULT_MODEL: str = "gemma-4-12b-it-qat@q4_k_xl"
PROBE_TIMEOUT_SEC: float = 1.0

CHUNK_MAX_TOKENS: int = 4096
CHUNK_TIMEOUT_SEC: int = 180
MULTIMODAL_TIMEOUT_SEC: int = 120

PRUNE_MAX_TOKENS: int = 4000
PRUNE_TIMEOUT_SEC: int = 600

SUMMARIZER_MAX_TOKENS: int = 4096
SUMMARIZER_TIMEOUT_SEC: int = 600

ENTITY_CONTEXT_MAX_TOKENS: int = 300

DEFAULT_TEMPERATURE: float = 0.1
VISION_TEMPERATURE: float = 0.2
MAX_RETRIES: int = 2

PRUNE_MIN_INPUT: int = 60
PRUNE_TARGET_MIN: int = 40
PRUNE_TARGET_MAX: int = 60

DEDUP_MIN_GAP_SEC: int = 120
DEDUP_MAX_GAP_SEC: int = 600
STAMP_COLLISION_SEC: int = 45

DEFAULT_GROUP_SIZE: int = 4
DEFAULT_BLOCK_SIZE: int = 2400
BYTE_CAP_LIMIT: int = 3500


def reload_config() -> None:
    """Reload all module constants from active _CONFIG and os.environ."""
    global PRIMARY_HOST, DEFAULT_PORT, DEFAULT_CHAT_PATH, DEFAULT_MODEL, PROBE_TIMEOUT_SEC
    global CHUNK_MAX_TOKENS, CHUNK_TIMEOUT_SEC, MULTIMODAL_TIMEOUT_SEC
    global PRUNE_MAX_TOKENS, PRUNE_TIMEOUT_SEC, SUMMARIZER_MAX_TOKENS, SUMMARIZER_TIMEOUT_SEC
    global ENTITY_CONTEXT_MAX_TOKENS, DEFAULT_TEMPERATURE, VISION_TEMPERATURE, MAX_RETRIES
    global PRUNE_MIN_INPUT, PRUNE_TARGET_MIN, PRUNE_TARGET_MAX
    global DEDUP_MIN_GAP_SEC, DEDUP_MAX_GAP_SEC, STAMP_COLLISION_SEC
    global DEFAULT_GROUP_SIZE, DEFAULT_BLOCK_SIZE, BYTE_CAP_LIMIT

    PRIMARY_HOST = cfg_str("primary_host", "100.115.25.30")
    DEFAULT_PORT = cfg_int("port", 1234)
    DEFAULT_CHAT_PATH = cfg_str("chat_path", "/v1/chat/completions")
    DEFAULT_MODEL = cfg_str("default_model", "gemma-4-12b-it-qat@q4_k_xl")
    PROBE_TIMEOUT_SEC = cfg_float("probe_timeout_sec", 1.0)

    CHUNK_MAX_TOKENS = cfg_int("chunk_max_tokens", 4096)
    CHUNK_TIMEOUT_SEC = cfg_int("chunk_timeout_sec", 180)
    MULTIMODAL_TIMEOUT_SEC = cfg_int("multimodal_timeout_sec", 120)

    PRUNE_MAX_TOKENS = cfg_int("prune_max_tokens", 4000)
    PRUNE_TIMEOUT_SEC = cfg_int("prune_timeout_sec", 600)

    SUMMARIZER_MAX_TOKENS = cfg_int("summarizer_max_tokens", 4096)
    SUMMARIZER_TIMEOUT_SEC = cfg_int("summarizer_timeout_sec", 600)

    ENTITY_CONTEXT_MAX_TOKENS = cfg_int("entity_context_max_tokens", 300)

    DEFAULT_TEMPERATURE = cfg_float("temperature", 0.1)
    VISION_TEMPERATURE = cfg_float("vision_temperature", 0.2)
    MAX_RETRIES = cfg_int("max_retries", 2)

    PRUNE_MIN_INPUT = cfg_int("prune_min_input", 60)
    PRUNE_TARGET_MIN = cfg_int("prune_target_min", 40)
    PRUNE_TARGET_MAX = cfg_int("prune_target_max", 60)

    DEDUP_MIN_GAP_SEC = cfg_int("dedup_min_gap_sec", 120)
    DEDUP_MAX_GAP_SEC = cfg_int("dedup_max_gap_sec", 600)
    STAMP_COLLISION_SEC = cfg_int("stamp_collision_sec", 45)

    DEFAULT_GROUP_SIZE = cfg_int("group_size", 4)
    DEFAULT_BLOCK_SIZE = cfg_int("block_size", 2400)
    BYTE_CAP_LIMIT = cfg_int("byte_cap_limit", 3500)


# Initialize from default config.json
load_config(SKILL_CONFIG_PATH, override=False)
