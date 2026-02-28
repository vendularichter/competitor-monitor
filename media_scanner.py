"""
Media scanner - monitors industry news for competitor mentions.
Only reports unique article URLs (not homepage mentions).
Tracks week-over-week changes to only show NEW mentions.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import (
    DATA_DIR,
    MEDIA_SEARCH_TERMS,
    MEDIA_SOURCES,
    REQUEST_DELAY,
)

# Sites that need browser rendering to bypass bot protection
BROWSER_REQUIRED_SITES = [
    "sbcnews.co.uk",
    "egr.global",
    "next.io",
    "esportsinsider.com",
]


class MediaScanner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })
        self.browser = None
        self.browser_context = None

    def _needs_browser(self, url: str) -> bool:
        """Check if URL requires browser rendering."""
        for site in BROWSER_REQUIRED_SITES:
            if site in url:
                return True
        return False

    def _get_browser(self):
        """Lazy-load Playwright browser."""
        if self.browser is None:
            try:
                from playwright.sync_api import sync_playwright
                self._playwright = sync_playwright().start()
                self.browser = self._playwright.chromium.launch(headless=True)
                self.browser_context = self.browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
            except Exception as e:
                print(f"  Warning: Could not start browser: {e}")
                return None
        return self.browser_context

    def _fetch_with_browser(self, url: str) -> str | None:
        """Fetch page using real browser (bypasses bot protection)."""
        context = self._get_browser()
        if not context:
            return None

        try:
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            # Wait a bit for dynamic content
            page.wait_for_timeout(2000)
            html = page.content()
            page.close()
            return html
        except Exception as e:
            print(f"  Browser error fetching {url}: {e}")
            return None

    def close(self):
        """Clean up browser resources."""
        if self.browser:
            self.browser.close()
            self._playwright.stop()

    def fetch_page(self, url: str) -> str | None:
        """Fetch a page and return its HTML."""
        # Use browser for protected sites
        if self._needs_browser(url):
            print(f"    (using browser for bot protection)")
            return self._fetch_with_browser(url)

        # Regular requests for other sites
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"  Error fetching {url}: {e}")
            return None

    def is_article_url(self, url: str, base_url: str) -> bool:
        """Check if URL is a unique article (not the main page or category page)."""
        parsed_url = urlparse(url)
        parsed_base = urlparse(base_url)

        # Must be same domain (handle www vs non-www)
        url_domain = parsed_url.netloc.replace("www.", "")
        base_domain = parsed_base.netloc.replace("www.", "")
        if url_domain != base_domain:
            return False

        path = parsed_url.path.rstrip("/")
        base_path = parsed_base.path.rstrip("/")

        # Skip if it's the same as base URL
        if path == base_path or path == "":
            return False

        # Skip common non-article patterns
        skip_patterns = [
            r"^/category/",
            r"^/tag/",
            r"^/author/",
            r"^/page/\d+",
            r"^/about",
            r"^/contact",
            r"^/privacy",
            r"^/terms",
            r"^/search",
            r"^/login",
            r"^/register",
        ]
        for pattern in skip_patterns:
            if re.search(pattern, path, re.I):
                return False

        # Should have enough path depth (likely an article)
        path_parts = [p for p in path.split("/") if p]
        return len(path_parts) >= 1

    def extract_articles(self, html: str, base_url: str) -> list[dict]:
        """Extract article titles and links from a page."""
        soup = BeautifulSoup(html, "html.parser")
        articles = []

        # Common article selectors (order matters - more specific first)
        article_selectors = [
            "article.card-post",  # EGR Global
            ".card-post",         # EGR Global fallback
            "article",
            ".article",
            ".post",
            ".news-item",
            ".entry",
            ".card",
            "[class*='article']",
            "[class*='post']",
            "[class*='news']",
        ]

        seen_urls = set()

        for selector in article_selectors:
            for element in soup.select(selector):
                # Try to find title element with a link (most reliable)
                title_el = element.select_one("h1 a[href], h2 a[href], h3 a[href], h4 a[href], .title a[href], [class*='title'] a[href]")

                if title_el:
                    # Title link found - use this URL (most accurate)
                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                else:
                    # Fallback: find title text and separate link
                    title_text_el = element.select_one("h1, h2, h3, h4, .title, [class*='title']")
                    title = title_text_el.get_text(strip=True) if title_text_el else None

                    # Look for main article link (prefer links with long text)
                    link_el = None
                    for a in element.select("a[href]"):
                        a_text = a.get_text(strip=True)
                        # Prefer links with substantial text (likely article title)
                        if len(a_text) > 20:
                            link_el = a
                            break

                    if not link_el:
                        link_el = element.select_one("a[href]")

                    if link_el:
                        href = link_el.get("href", "")
                        if not title:
                            title = link_el.get_text(strip=True)
                    else:
                        continue

                # Make absolute URL
                if href.startswith("//"):
                    # Protocol-relative URL (e.g., //www.egr.global/...)
                    href = "https:" + href
                elif href.startswith("/"):
                    from urllib.parse import urljoin
                    href = urljoin(base_url, href)

                # Only include unique article URLs
                if (href and
                    href not in seen_urls and
                    href.startswith("http") and
                    self.is_article_url(href, base_url)):

                    seen_urls.add(href)

                    if title and len(title) > 10:
                        articles.append({
                            "title": title[:200],
                            "url": href,
                        })

        return articles[:50]

    def search_for_terms(self, text: str, terms: list[str]) -> list[str]:
        """Search text for specific terms and return matched terms only.
        Uses word boundary matching to avoid false positives like 'SIS' in 'Mississippi'.
        """
        matched_terms = []

        for term in terms:
            # Use word boundary regex to match whole words/phrases only
            # \b matches word boundaries (start/end of word)
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                matched_terms.append(term)

        return matched_terms

    def scan_source(self, source: dict) -> dict:
        """Scan a media source for competitor mentions in articles only."""
        name = source["name"]
        url = source["url"]
        category = source.get("category", "Unknown")

        print(f"  Scanning {name}...")

        html = self.fetch_page(url)
        if not html:
            return {
                "name": name,
                "url": url,
                "category": category,
                "error": "Failed to fetch",
                "articles": [],
            }

        # Find article links
        articles = self.extract_articles(html, url)
        print(f"    Found {len(articles)} articles")

        # Only check article titles for mentions (not main page)
        articles_with_mentions = []
        for article in articles:
            matched_terms = self.search_for_terms(article["title"], MEDIA_SEARCH_TERMS)
            if matched_terms:
                articles_with_mentions.append({
                    "url": article["url"],
                    "title": article["title"],
                    "terms": matched_terms,
                })

        time.sleep(REQUEST_DELAY)

        return {
            "name": name,
            "url": url,
            "category": category,
            "articles_found": len(articles),
            "articles_with_mentions": articles_with_mentions,
            "scanned_at": datetime.now().isoformat(),
        }


def scan_all_media() -> dict:
    """Scan all configured media sources."""
    scanner = MediaScanner()
    results = {}

    print("\nScanning media sources for competitor mentions...")

    try:
        for source in MEDIA_SOURCES:
            result = scanner.scan_source(source)
            results[source["name"]] = result

            mentions_count = len(result.get("articles_with_mentions", []))
            if mentions_count:
                print(f"    Found {mentions_count} articles with mentions!")
    finally:
        # Clean up browser resources
        scanner.close()

    return results


def save_media_scan(results: dict, filename: str = None) -> str:
    """Save media scan results to JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"media_scan_{timestamp}.json"

    filepath = os.path.join(DATA_DIR, filename)

    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved media scan to {filepath}")
    return filepath


def get_latest_media_scans(count: int = 2) -> list[str]:
    """Get the most recent media scan files."""
    if not os.path.exists(DATA_DIR):
        return []

    files = [f for f in os.listdir(DATA_DIR) if f.startswith("media_scan_") and f.endswith(".json")]
    files.sort(reverse=True)
    return [os.path.join(DATA_DIR, f) for f in files[:count]]


def load_media_scan(filepath: str) -> dict:
    """Load media scan from JSON file."""
    with open(filepath) as f:
        return json.load(f)


def get_new_mentions(current: dict, previous: dict) -> dict:
    """Compare two scans and return only NEW mentions (week-over-week)."""
    new_mentions = {}

    # Get all previously seen article URLs
    prev_urls = set()
    for source_name, data in previous.items():
        for article in data.get("articles_with_mentions", []):
            prev_urls.add(article["url"])

    # Find new articles not in previous scan
    for source_name, data in current.items():
        new_articles = []
        for article in data.get("articles_with_mentions", []):
            if article["url"] not in prev_urls:
                new_articles.append(article)

        if new_articles:
            new_mentions[source_name] = {
                "category": data.get("category", ""),
                "articles": new_articles,
            }

    return new_mentions


def generate_media_report(results: dict, new_only: dict = None) -> str:
    """Generate a human-readable media scan report."""
    report_lines = [
        "# Media Scan Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    # If we have week-over-week data, show new mentions only
    if new_only is not None:
        if not new_only:
            report_lines.append("No NEW competitor mentions this week.")
            return "\n".join(report_lines)

        total = sum(len(d["articles"]) for d in new_only.values())
        report_lines.append(f"## {total} NEW mentions this week")
        report_lines.append("")

        for source_name, data in new_only.items():
            report_lines.append(f"### {source_name} ({data['category']})")
            for article in data["articles"]:
                terms = ", ".join(article["terms"])
                report_lines.append(f"- [{article['title'][:60]}...]({article['url']})")
                report_lines.append(f"  Mentions: {terms}")
            report_lines.append("")

        return "\n".join(report_lines)

    # Otherwise show all mentions from current scan
    total_mentions = 0
    sources_with_mentions = []

    for source_name, data in results.items():
        articles = data.get("articles_with_mentions", [])
        if articles:
            total_mentions += len(articles)
            sources_with_mentions.append({
                "name": source_name,
                "category": data.get("category", ""),
                "articles": articles,
            })

    if not sources_with_mentions:
        report_lines.append("No competitor mentions found in media sources.")
        return "\n".join(report_lines)

    report_lines.append(f"## Found {total_mentions} articles across {len(sources_with_mentions)} sources")
    report_lines.append("")

    for source in sources_with_mentions:
        report_lines.append(f"### {source['name']} ({source['category']})")
        for article in source["articles"][:5]:
            terms = ", ".join(article["terms"])
            report_lines.append(f"- [{article['title'][:60]}...]({article['url']})")
            report_lines.append(f"  Mentions: {terms}")
        report_lines.append("")

    return "\n".join(report_lines)


if __name__ == "__main__":
    print("Starting media scan...")
    results = scan_all_media()
    save_media_scan(results)

    # Check for week-over-week changes
    scan_files = get_latest_media_scans(2)
    if len(scan_files) >= 2:
        previous = load_media_scan(scan_files[1])
        new_mentions = get_new_mentions(results, previous)
        print("\n" + generate_media_report(results, new_mentions))
    else:
        print("\n" + generate_media_report(results))

    print("\nDone!")
