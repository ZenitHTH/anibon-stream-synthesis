"""Lightweight DuckDuckGo web search with local JSON caching.

Used by anibon-timestamper-local to verify ambiguous character names,
game updates, or anime titles without external paid API keys.
"""
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional


def load_search_cache(cache_file: Path) -> Dict[str, List[dict]]:
    """Load cached query results from JSON file."""
    if cache_file and cache_file.exists():
        try:
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_search_cache(cache_file: Path, cache: Dict[str, List[dict]]) -> None:
    """Save query results cache to JSON file."""
    if not cache_file:
        return
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def search_duckduckgo(query: str, max_results: int = 3, timeout: int = 10) -> List[dict]:
    """Execute DuckDuckGo Lite HTML search and parse top results.

    Zero third-party dependencies; uses standard library urllib.
    """
    encoded_q = urllib.parse.quote_plus(query)
    url = f"https://lite.duckduckgo.com/lite/"
    data = f"q={encoded_q}".encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    results = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")

        # DuckDuckGo Lite renders results in tables with class="result-link" and class="result-snippet"
        # Parse titles & links
        link_matches = re.findall(r'<a class=["\']result-link["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', content, re.I | re.S)
        snippet_matches = re.findall(r'<td class=["\']result-snippet["\'][^>]*>(.*?)</td>', content, re.I | re.S)

        for i in range(min(len(link_matches), max_results)):
            link, raw_title = link_matches[i]
            title = html.unescape(re.sub(r"<[^>]+>", "", raw_title).strip())
            raw_snippet = snippet_matches[i] if i < len(snippet_matches) else ""
            snippet = html.unescape(re.sub(r"<[^>]+>", "", raw_snippet).strip())
            snippet = re.sub(r"\s+", " ", snippet)

            if title:
                results.append({
                    "title": title,
                    "snippet": snippet,
                    "url": link,
                })
    except Exception:
        # Fallback empty on network errors
        return []

    return results


def build_entity_query(entity: str, domain: Optional[str] = None) -> str:
    """Format targeted search query with domain hints to get wiki/fandom hits."""
    clean = entity.strip()
    d_lower = (domain or "").lower()

    if "toku" in d_lower or "rider" in d_lower:
        return f"{clean} kamen rider tokusatsu wiki"
    elif "game" in d_lower or "gacha" in d_lower:
        return f"{clean} game wiki fandom"
    elif "anime" in d_lower:
        return f"{clean} anime characters wiki"
    return f"{clean} wiki"


def format_search_context(entity: str, results: List[dict]) -> str:
    """Format search results into a clean markdown block for prompt injection."""
    if not results:
        return ""
    lines = [f"## VERIFIED WEB CONTEXT: {entity}"]
    for res in results[:2]:
        t = res.get("title", "")
        s = res.get("snippet", "")
        if s:
            lines.append(f"- **{t}**: {s}")
    return "\n".join(lines)


def search_entity_context(
    entity: str,
    domain: Optional[str] = None,
    cache_file: Optional[Path] = None,
    max_results: int = 2,
) -> str:
    """Search DuckDuckGo with caching and return prompt snippet."""
    if not entity or not entity.strip():
        return ""

    key = entity.strip().lower()
    cache = load_search_cache(cache_file) if cache_file else {}

    if key in cache:
        return format_search_context(entity, cache[key])

    query = build_entity_query(entity, domain)
    results = search_duckduckgo(query, max_results=max_results)

    if results:
        cache[key] = results
        if cache_file:
            save_search_cache(cache_file, cache)
        return format_search_context(entity, results)

    return ""
