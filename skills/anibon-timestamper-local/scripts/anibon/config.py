"""Zero-dependency .env loader and configuration management for anibon-timestamper-local."""
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional

# Locate skill-level default .env (skills/anibon-timestamper-local/.env)
SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_DOTENV_PATH = SKILL_ROOT / ".env"


def _clean_env_val(raw_val: str) -> str:
    """Strip inline comments and wrapping quotes from a raw .env value."""
    val = raw_val.strip()
    if not val:
        return ""

    # Quoted string: match up to closing quote, ignore trailing comment
    if val.startswith('"'):
        m = re.match(r'^"([^"]*)"', val)
        if m:
            return m.group(1)
    elif val.startswith("'"):
        m = re.match(r"^'([^']*)'", val)
        if m:
            return m.group(1)

    # Unquoted string: strip inline comments if any
    if " #" in val:
        val = val.split(" #", 1)[0].strip()
    elif "\t#" in val:
        val = val.split("\t#", 1)[0].strip()

    return val


def parse_dotenv(content: str) -> Dict[str, str]:
    """Parse .env content into a dictionary."""
    data: Dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, raw_val = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        val = _clean_env_val(raw_val)
        data[key] = val
    return data


def load_dotenv(path: Optional[Path] = None, override: bool = False) -> Dict[str, str]:
    """Load .env file into os.environ.
    
    If path is omitted, loads SKILL_DOTENV_PATH if it exists.
    If override is False, existing os.environ keys take precedence.
    """
    env_path = Path(path) if path else SKILL_DOTENV_PATH
    if not env_path or not env_path.is_file():
        return {}

    try:
        content = env_path.read_text(encoding="utf-8")
        parsed = parse_dotenv(content)
        for k, v in parsed.items():
            if override or k not in os.environ:
                os.environ[k] = v
        if override:
            reload_config()
        return parsed
    except Exception as e:
        print(f"[config] Warning: Failed to read {env_path}: {e}", file=sys.stderr)
        return {}


def env_str(key: str, default: str) -> str:
    """Retrieve string environment variable or return default."""
    val = os.environ.get(key)
    if val is None or val == "":
        return default
    return val


def env_int(key: str, default: int) -> int:
    """Retrieve integer environment variable or return default on error/empty."""
    val = os.environ.get(key)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def env_float(key: str, default: float) -> float:
    """Retrieve float environment variable or return default on error/empty."""
    val = os.environ.get(key)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ── Configuration Constants ──────────────────────────────────────────────────
PRIMARY_HOST: str = "100.115.25.30"
DEFAULT_PORT: int = 1234
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
    """Reload all module constants from os.environ."""
    global PRIMARY_HOST, DEFAULT_PORT, DEFAULT_MODEL, PROBE_TIMEOUT_SEC
    global CHUNK_MAX_TOKENS, CHUNK_TIMEOUT_SEC, MULTIMODAL_TIMEOUT_SEC
    global PRUNE_MAX_TOKENS, PRUNE_TIMEOUT_SEC, SUMMARIZER_MAX_TOKENS, SUMMARIZER_TIMEOUT_SEC
    global ENTITY_CONTEXT_MAX_TOKENS, DEFAULT_TEMPERATURE, VISION_TEMPERATURE, MAX_RETRIES
    global PRUNE_MIN_INPUT, PRUNE_TARGET_MIN, PRUNE_TARGET_MAX
    global DEDUP_MIN_GAP_SEC, DEDUP_MAX_GAP_SEC, STAMP_COLLISION_SEC
    global DEFAULT_GROUP_SIZE, DEFAULT_BLOCK_SIZE, BYTE_CAP_LIMIT

    PRIMARY_HOST = env_str("ANIBON_PRIMARY_HOST", "100.115.25.30")
    DEFAULT_PORT = env_int("ANIBON_PORT", 1234)
    DEFAULT_MODEL = env_str("ANIBON_DEFAULT_MODEL", "gemma-4-12b-it-qat@q4_k_xl")
    PROBE_TIMEOUT_SEC = env_float("ANIBON_PROBE_TIMEOUT_SEC", 1.0)

    CHUNK_MAX_TOKENS = env_int("ANIBON_CHUNK_MAX_TOKENS", 4096)
    CHUNK_TIMEOUT_SEC = env_int("ANIBON_CHUNK_TIMEOUT_SEC", 180)
    MULTIMODAL_TIMEOUT_SEC = env_int("ANIBON_MULTIMODAL_TIMEOUT_SEC", 120)

    PRUNE_MAX_TOKENS = env_int("ANIBON_PRUNE_MAX_TOKENS", 4000)
    PRUNE_TIMEOUT_SEC = env_int("ANIBON_PRUNE_TIMEOUT_SEC", 600)

    SUMMARIZER_MAX_TOKENS = env_int("ANIBON_SUMMARIZER_MAX_TOKENS", 4096)
    SUMMARIZER_TIMEOUT_SEC = env_int("ANIBON_SUMMARIZER_TIMEOUT_SEC", 600)

    ENTITY_CONTEXT_MAX_TOKENS = env_int("ANIBON_ENTITY_CONTEXT_MAX_TOKENS", 300)

    DEFAULT_TEMPERATURE = env_float("ANIBON_TEMPERATURE", 0.1)
    VISION_TEMPERATURE = env_float("ANIBON_VISION_TEMPERATURE", 0.2)
    MAX_RETRIES = env_int("ANIBON_MAX_RETRIES", 2)

    PRUNE_MIN_INPUT = env_int("ANIBON_PRUNE_MIN_INPUT", 60)
    PRUNE_TARGET_MIN = env_int("ANIBON_PRUNE_TARGET_MIN", 40)
    PRUNE_TARGET_MAX = env_int("ANIBON_PRUNE_TARGET_MAX", 60)

    DEDUP_MIN_GAP_SEC = env_int("ANIBON_DEDUP_MIN_GAP_SEC", 120)
    DEDUP_MAX_GAP_SEC = env_int("ANIBON_DEDUP_MAX_GAP_SEC", 600)
    STAMP_COLLISION_SEC = env_int("ANIBON_STAMP_COLLISION_SEC", 45)

    DEFAULT_GROUP_SIZE = env_int("ANIBON_GROUP_SIZE", 4)
    DEFAULT_BLOCK_SIZE = env_int("ANIBON_BLOCK_SIZE", 2400)
    BYTE_CAP_LIMIT = env_int("ANIBON_BYTE_CAP_LIMIT", 3500)


# Initialize from default .env
load_dotenv(SKILL_DOTENV_PATH, override=False)
reload_config()
