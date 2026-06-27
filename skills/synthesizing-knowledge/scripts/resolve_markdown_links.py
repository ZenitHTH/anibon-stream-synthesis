"""
resolve_markdown_links.py

Pass 1: Scans a Markdown file for Google Grounding Smart Redirect URLs, resolves them,
        and formats them to contain both the original Smart Redirect Link and the resolved Direct Link.

Pass 2: Scans the References section for homepage-only URLs (path is "/" or empty)
        and prints [HOMEPAGE WARNING] for each one so the agent knows they need a follow-up search.

Pass 3: Validates HTTP status for all URLs to detect hallucinated/broken links (404, etc.)
        and prints [BROKEN LINK WARNING].

Usage:
    python resolve_markdown_links.py <path-to-markdown-file>
"""

import sys
import os
import re
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed


# --- Pass 1: Resolve Vertex AI / Smart Redirect URLs ---

def resolve_url(url, depth=0):
    if depth > 5:
        print(f"[resolve_url] Maximum redirect depth (5) reached for URL: {url}. Returning last URL.")
        return url

    parsed_url = urllib.parse.urlparse(url)
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )

    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def http_error_301(self, req, fp, code, msg, hdrs): return fp
        def http_error_302(self, req, fp, code, msg, hdrs): return fp
        def http_error_303(self, req, fp, code, msg, hdrs): return fp
        def http_error_307(self, req, fp, code, msg, hdrs): return fp
        def http_error_308(self, req, fp, code, msg, hdrs): return fp

    opener = urllib.request.build_opener(NoRedirectHandler)
    try:
        req.get_method = lambda: 'HEAD'
        with opener.open(req, timeout=5) as response:
            if response.status in (301, 302, 303, 307, 308):
                location = response.headers.get('Location')
                if location:
                    if not location.startswith('http'):
                        location = urllib.parse.urljoin(url, location)
                    return resolve_url(location, depth + 1)
            return url
    except Exception as e:
        try:
            req2 = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with opener.open(req2, timeout=5) as response:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.headers.get('Location')
                    if location:
                        if not location.startswith('http'):
                            location = urllib.parse.urljoin(url, location)
                        return resolve_url(location, depth + 1)
                return url
        except Exception as ge:
            print(f"-> Failed to resolve: {ge}")
            return url


# --- Pass 2: Homepage-only URL detection in References section ---

def is_homepage_url(url_string):
    try:
        parsed = urllib.parse.urlparse(url_string)
        clean_path = parsed.path.rstrip('/')
        return clean_path == ''
    except Exception:
        return False


def audit_homepage_urls(content):
    homepage_matches = []
    seen_urls = set()

    ref_line_regex = re.compile(r'^\s*-\s*\[\d+\]\s*\[([^\]]+)\]\((https?://[^\)]+)\)', re.MULTILINE)
    plain_link_regex = re.compile(r'^\s*-\s*\[([^\]]+)\]\((https?://[^\)]+)\)', re.MULTILINE)

    for match in ref_line_regex.finditer(content):
        link_text, url = match.group(1), match.group(2)
        if url not in seen_urls and is_homepage_url(url):
            homepage_matches.append({'text': link_text, 'url': url})
            seen_urls.add(url)

    for match in plain_link_regex.finditer(content):
        link_text, url = match.group(1), match.group(2)
        if url not in seen_urls and is_homepage_url(url):
            homepage_matches.append({'text': link_text, 'url': url})
            seen_urls.add(url)

    if homepage_matches:
        print(f"\n=== HOMEPAGE URL AUDIT: {len(homepage_matches)} homepage-only URL(s) found ===")
        print("These URLs point to a domain root with no article path.")
        print("They require a follow-up search_web (e.g., site:domain.com [topic]) before finalizing the report.\n")
        for item in homepage_matches:
            print(f"[HOMEPAGE WARNING] \"{item['text']}\" -> {item['url']}")
        print('')
    else:
        print("\n=== HOMEPAGE URL AUDIT: All reference URLs have specific paths. No homepage-only URLs found. ===\n")

    return len(homepage_matches)


# --- Pass 3: Broken Link (404) Detection ---

def check_link_status(item):
    url = item['url']
    text = item['text']
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    req.get_method = lambda: 'HEAD'
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return {'url': url, 'text': text, 'status': response.status, 'error': None}
    except urllib.error.HTTPError as e:
        return {'url': url, 'text': text, 'status': e.code, 'error': str(e)}
    except Exception as e:
        # Fallback to GET just in case HEAD is rejected
        try:
            req.get_method = lambda: 'GET'
            with urllib.request.urlopen(req, timeout=5) as response:
                return {'url': url, 'text': text, 'status': response.status, 'error': None}
        except urllib.error.HTTPError as e2:
            return {'url': url, 'text': text, 'status': e2.code, 'error': str(e2)}
        except Exception as e2:
            return {'url': url, 'text': text, 'status': 0, 'error': str(e2)}

def audit_broken_links(content):
    link_regex = re.compile(r'\[([^\]]+)\]\((https?://[^\)]+)\)')
    links_to_check = []
    seen_urls = set()
    
    for match in link_regex.finditer(content):
        text = match.group(1)
        url = match.group(2)
        if 'vertexaisearch.cloud.google.com' not in url and url not in seen_urls:
            links_to_check.append({'text': text, 'url': url})
            seen_urls.add(url)
            
    if not links_to_check:
        return 0
        
    print(f"\nRunning Pass 3 (Broken Link Audit) on {len(links_to_check)} unique URL(s)...")
    broken_count = 0
    results = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(check_link_status, item): item for item in links_to_check}
        for future in as_completed(future_to_url):
            results.append(future.result())
            
    for res in results:
        status = res['status']
        error = res['error']
        if status == 404 or status == 400 or (status == 0 and 'timeout' not in str(error).lower()):
            print(f"[BROKEN LINK WARNING] \"{res['text']}\" -> {res['url']} (Status: {status or error})")
            broken_count += 1
            
    if broken_count == 0:
        print("=== BROKEN LINK AUDIT: No 404/broken links detected. ===")
    else:
        print(f"\n=== BROKEN LINK AUDIT: {broken_count} broken link(s) found! ===")
        print("These URLs may be hallucinated or moved. You MUST perform a follow-up search to replace them.")
        
    return broken_count

# --- Main ---

def main():
    if len(sys.argv) < 2:
        print("Usage: python resolve_markdown_links.py <path-to-markdown-file>")
        sys.exit(1)

    file_path = os.path.abspath(sys.argv[1])
    if not os.path.exists(file_path):
        print(f"File does not exist: {file_path}")
        sys.exit(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # --- Pass 1: Smart Redirect & Webcache Resolution ---
    # 1. Vertex AI Smart Links
    vertex_regex = r'\[([^\]]+)\]\((https://vertexaisearch\.cloud\.google\.com/grounding-api-redirect/[a-zA-Z0-9_=-]+)\)'
    # 2. Google Webcache Links
    webcache_regex = r'\[([^\]]+)\]\((https?://webcache\.googleusercontent\.com/search\?q=cache:[^)]+)\)'

    content_changed = False
    success_count = 0

    # Resolve Vertex AI Links
    vertex_matches = list(re.finditer(vertex_regex, content))
    if vertex_matches:
        print(f"Pass 1: Found {len(vertex_matches)} Vertex AI smart link(s).")
        for match in vertex_matches:
            full_match = match.group(0)
            text = match.group(1)
            url = match.group(2)
            print(f"Resolving: {url}")
            real_url = resolve_url(url)
            if real_url != url:
                # Replace cleanly, no dual links
                content = content.replace(full_match, f"[{text}]({real_url})")
                success_count += 1
                content_changed = True
                print(f"-> Extracted: {real_url}")

    # Resolve Webcache Links
    webcache_matches = list(re.finditer(webcache_regex, content))
    if webcache_matches:
        print(f"Pass 1: Found {len(webcache_matches)} Webcache link(s).")
        for match in webcache_matches:
            full_match = match.group(0)
            text = match.group(1)
            url = match.group(2)
            print(f"Extracting canonical from: {url}")
            
            parsed = urllib.parse.urlparse(url)
            q_param = urllib.parse.parse_qs(parsed.query).get('q', [''])[0]
            # Extract http/https URL from the q parameter
            url_match = re.search(r'(https?://[^\s&+]+)', q_param)
            
            if url_match:
                real_url = url_match.group(1)
                content = content.replace(full_match, f"[{text}]({real_url})")
                success_count += 1
                content_changed = True
                print(f"-> Extracted: {real_url}")
            else:
                print("-> Could not parse canonical link from webcache URL.")

    if content_changed:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\nPass 1 Done! Updated {success_count} links to their canonical versions.")
    else:
        print("Pass 1: No new smart redirect or webcache updates were made to the file.")

    # --- Pass 2: Homepage URL Audit ---
    print("\nRunning Pass 2 (Homepage URL Audit)...")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    homepage_count = audit_homepage_urls(content)

    # --- Pass 3: Broken Link Audit ---
    broken_count = audit_broken_links(content)

    if homepage_count > 0 or broken_count > 0:
        print(f"\nACTION REQUIRED: {homepage_count} homepage-only URL(s) and {broken_count} broken link(s) need follow-up searches before finalizing the report.")

    print("\n=== SCRIPT COMPLETE ===")


if __name__ == '__main__':
    main()
