#!/usr/bin/env python3
"""Build complete categorized anibon_wiki/wiki/index.md from live wiki/ pages."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

WIKI_DIR = Path(__file__).resolve().parents[1] / "wiki"
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.S)


def _read_meta(path: Path) -> Tuple[str, str, str]:
    """Return (title, upload_date, updated) from YAML frontmatter."""
    txt = path.read_text(encoding="utf-8", errors="replace")
    m = _FM_RE.match(txt)
    fm = m.group(1) if m else ""
    def grab(key: str, default: str = "") -> str:
        km = re.search(rf'^{key}:\s*"?([^"\n]+)"?', fm, re.M)
        return km.group(1).strip() if km else default
    return grab("title", path.stem), grab("upload_date", ""), grab("updated", "2026-11-21")


def _list_folder(rel_dir: str) -> List[Tuple[str, str, str]]:
    """Return sorted (slug, title, date) tuples for markdown pages in wiki/<rel_dir>."""
    rows: List[Tuple[str, str, str]] = []
    target = WIKI_DIR / rel_dir
    if not target.is_dir():
        return rows
    for p in sorted(target.glob("*.md")):
        title, up_date, updated = _read_meta(p)
        rows.append((p.stem, title, up_date or updated))
    return rows


def main() -> int:
    games = _list_folder("games")
    entities = _list_folder("entities")
    topics = _list_folder("topics")
    pipes = _list_folder("engineering/pipelines")
    pms = _list_folder("engineering/post-mortems")
    scripts = _list_folder("engineering/scripts")
    all_sources = _list_folder("sources")

    code_sources = [r for r in all_sources if not r[0].startswith("stream-")]
    stream_sources = sorted([r for r in all_sources if r[0].startswith("stream-")], key=lambda x: (x[2], x[0]), reverse=True)

    out: List[str] = [
        "---",
        'title: "Anibon Stream & Engineering Wiki — Master Index"',
        'category: "index"',
        'updated: "2026-11-21"',
        'tags: ["index", "catalog"]',
        'status: "active"',
        "---",
        "",
        "# Anibon Stream & Engineering Wiki — Master Index",
        "",
        f"- **Total Knowledge Base**: `{len(stream_sources)}` Livestreams | `{len(games)}` Games | `{len(entities)}` Entities | `{len(topics)}` Topics | `{len(pipes) + len(pms) + len(scripts)}` Engineering Docs | `{len(code_sources)}` Code Snapshots",
        "- **High-Level Synthesis**: [[overview]]",
        "- **Operation Log**: [[log]]",
        "- **Schema & Rules**: [CLAUDE.md](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/CLAUDE.md) | [AGENTS.md](file:///Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/anibon_wiki/AGENTS.md)",
        "",
        "---",
        "",
        f"## 1. Thematic Topics (`wiki/topics/` — {len(topics)})",
    ]
    out.extend(f"- [[{s}]] — {t}" for s, t, _ in topics)

    out.extend(["", f"## 2. Games & Franchises (`wiki/games/` — {len(games)})"])
    out.extend(f"- [[{s}]] — {t}" for s, t, _ in games)

    out.extend(["", f"## 3. Characters, Studios & Entities (`wiki/entities/` — {len(entities)})"])
    out.extend(f"- [[{s}]] — {t}" for s, t, _ in entities)

    out.extend(["", f"## 4. Python Scripts, Pipelines & Post-Mortems (`wiki/engineering/` — {len(pipes) + len(pms) + len(scripts)})"])
    out.append("### Pipelines")
    out.extend(f"- [[{s}]] — {t}" for s, t, _ in pipes)
    out.append("### Post-Mortems")
    out.extend(f"- [[{s}]] — {t}" for s, t, _ in pms)
    out.append("### Python Scripts & CLI Tools")
    out.extend(f"- [[{s}]] — {t}" for s, t, _ in scripts)

    out.extend(["", f"## 5. Engineering Source Snapshots (`wiki/sources/` — {len(code_sources)})"])
    out.extend(f"- [[{s}]] — {t}" for s, t, _ in code_sources)

    out.extend(["", f"## 6. ANIBON Livestream Catalog (`wiki/sources/stream-*.md` — {len(stream_sources)}, Newest First)"])
    out.append("")
    out.append("| Upload Date | Wiki Page | Stream Title |")
    out.append("| :---: | :--- | :--- |")
    for s, t, d in stream_sources:
        clean_t = t.replace("|", "\\|")
        out.append(f"| `{d}` | [[{s}]] | {clean_t} |")

    (WIKI_DIR / "index.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Rebuilt wiki/index.md with {len(stream_sources) + len(games) + len(entities) + len(topics) + len(pipes) + len(pms) + len(scripts) + len(code_sources)} cataloged pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
