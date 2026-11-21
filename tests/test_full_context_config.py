from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(_ROOT / "lib"))

from common import config
from chunk.state import load_chunk_livechat
from process.prompts import coalesce_chunk_items, load_world_identity_context


def test_coalesce_keeps_every_line_when_unlimited():
    items = [{"timestamp": f"00:00:{i:02d}", "text": f"t{i}"} for i in range(100)]
    assert len(coalesce_chunk_items(items, max_lines=0)) == 100


def test_default_config_is_full_context():
    assert config.COMPACT_CHUNK_MAX_LINES == 0
    assert config.LIVECHAT_MAX_LINES == 0
    assert config.WI_SNIPPET_LIMIT == 0


def test_livechat_unlimited(tmp_path):
    (tmp_path / "livechat").mkdir()
    lines = "\n".join(f"m{i}" for i in range(50))
    (tmp_path / "livechat" / "livechat_chunk_00.txt").write_text(lines, encoding="utf-8")
    assert len(load_chunk_livechat(tmp_path, "chunk_00").splitlines()) == 50


def test_wi_snippet_unlimited(tmp_path):
    ref = tmp_path / "Game.md"
    ref.write_text("x" * 5000, encoding="utf-8")
    out = load_world_identity_context({"best_file": "Game.md"}, tmp_path)
    assert "(truncated)" not in out and out.count("x") == 5000
