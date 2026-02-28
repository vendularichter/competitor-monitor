"""
Web crawler that discovers and fetches pages from competitor websites.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import (
    COMPETITORS,
    DATA_DIR,
    MAX_CRAWL_DEPTH,
    MAX_PAGES_PER_SITE,
    REQUEST_DELAY,
    USER_AGENT,
)


class WebCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.visited_urls = set()

    def is_same_domain(self, base_url: str, target_url: str) -> bool:
        """Check if target URL is on the same domain as base URL."""
        base_domain = urlparse(base_url).netloc
        target_domain = urlparse(target_url).netloc
        return base_domain == target_domain

    def normalize_url(self, url: str) -> str:
        """Normalize URL by removing fragments and trailing slashes."""
        parsed = urlparse(url)
        # Remove fragment and normalize
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return normalized.rstrip("/")

    def extract_links(self, html: str, base_url: str) -> list[str]:
        """Extract all links from HTML that are on the same domain."""
        soup = BeautifulSoup(html, "html.parser")
        links = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            # Convert relative URLs to absolute
            full_url = urljoin(base_url, href)
            normalized = self.normalize_url(full_url)

            # Only include same-domain links
            if self.is_same_domain(base_url, normalized):
                # Skip common non-content URLs
                skip_patterns = [
                    r"/login",
                    r"/signup",
                    r"/signin",
                    r"/logout",
                    r"/cart",
                    r"/checkout",
                    r"\.pdf$",
                    r"\.zip$",
                    r"\.exe$",
                    r"\?",
                    r"#",
                    r"mailto:",
                    r"tel:",
                    r"javascript:",
                ]
                if not any(re.search(p, normalized, re.I) for p in skip_patterns):
                    links.append(normalized)

        return list(set(links))

    def extract_text_content(self, html: str) -> str:
        """Extract meaningful text content from HTML."""
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Get text
        text = soup.get_text(separator=" ", strip=True)

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)

        return text

    def fetch_page(self, url: str) -> dict | None:
        """Fetch a single page and return its content."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            html = response.text
            text_content = self.extract_text_content(html)
            content_hash = hashlib.md5(text_content.encode()).hexdigest()

            return {
                "url": url,
                "status_code": response.status_code,
                "html": html,
                "text_content": text_content,
                "content_hash": content_hash,
                "fetched_at": datetime.now().isoformat(),
                "links": self.extract_links(html, url),
            }
        except requests.RequestException as e:
            print(f"  Error fetching {url}: {e}")
            return None

    def crawl_site(self, homepage: str, max_pages: int = None, max_depth: int = None) -> list[dict]:
        """Crawl a website starting from the homepage."""
        max_pages = max_pages or MAX_PAGES_PER_SITE
        max_depth = max_depth or MAX_CRAWL_DEPTH

        self.visited_urls = set()
        pages = []

        # Queue: (url, depth)
        queue = [(self.normalize_url(homepage), 0)]

        while queue and len(pages) < max_pages:
            url, depth = queue.pop(0)

            if url in self.visited_urls:
                continue

            self.visited_urls.add(url)
            print(f"  Crawling: {url} (depth {depth})")

            page_data = self.fetch_page(url)
            if page_data:
                pages.append(page_data)

                # Add new links to queue if not at max depth
                if depth < max_depth:
                    for link in page_data["links"]:
                        if link not in self.visited_urls:
                            queue.append((link, depth + 1))

            # Be polite
            time.sleep(REQUEST_DELAY)

        return pages

    def find_pricing_page(self, pages: list[dict]) -> dict | None:
        """Try to identify the pricing page from crawled pages."""
        pricing_keywords = ["pricing", "plans", "price", "cost", "subscription"]

        for page in pages:
            url_lower = page["url"].lower()
            if any(keyword in url_lower for keyword in pricing_keywords):
                return page

        # Check content if URL doesn't match
        for page in pages:
            content_lower = page["text_content"].lower()
            # Look for pricing indicators in content
            if any(
                phrase in content_lower
                for phrase in ["per month", "/mo", "pricing", "free tier", "enterprise plan"]
            ):
                return page

        return None


def find_keyword_matches(text: str, keywords: list[str]) -> list[dict]:
    """Find keyword matches in text with surrounding context."""
    matches = []
    text_lower = text.lower()

    for keyword in keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in text_lower:
            # Find position and extract context
            pos = text_lower.find(keyword_lower)
            start = max(0, pos - 100)
            end = min(len(text), pos + len(keyword) + 100)
            context = text[start:end]
            matches.append({
                "keyword": keyword,
                "context": f"...{context}..."
            })

    return matches


def crawl_all_competitors() -> dict:
    """Crawl all configured competitors and return results."""
    crawler = WebCrawler()
    results = {}

    for competitor in COMPETITORS:
        name = competitor["name"]
        homepage = competitor["homepage"]
        news_url = competitor.get("news_url")
        keywords = competitor.get("keywords", [])
        tier = competitor.get("tier", "Unknown")

        print(f"\n[{tier}] Crawling {name}...")

        # Crawl starting from news page if available, otherwise homepage
        start_url = news_url or homepage
        pages = crawler.crawl_site(start_url)
        print(f"  Found {len(pages)} pages")

        # Also fetch homepage if we started from news
        if news_url and homepage not in [p["url"] for p in pages]:
            homepage_data = crawler.fetch_page(homepage)
            if homepage_data:
                pages.insert(0, homepage_data)

        # Find or fetch pricing page
        pricing_page = None
        if competitor.get("pricing_url"):
            pricing_page = crawler.fetch_page(competitor["pricing_url"])
        else:
            pricing_page = crawler.find_pricing_page(pages)

        # Check for keyword alerts across all pages
        keyword_alerts = []
        for page in pages:
            matches = find_keyword_matches(page["text_content"], keywords)
            if matches:
                keyword_alerts.append({
                    "url": page["url"],
                    "matches": matches
                })

        results[name] = {
            "homepage": homepage,
            "news_url": news_url,
            "tier": tier,
            "keywords": keywords,
            "pages": pages,
            "pricing_page": pricing_page,
            "keyword_alerts": keyword_alerts,
            "crawled_at": datetime.now().isoformat(),
        }

        if keyword_alerts:
            print(f"  Found {len(keyword_alerts)} pages with keyword matches")

    return results


def save_crawl_data(results: dict, filename: str = None) -> str:
    """Save crawl results to JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"crawl_{timestamp}.json"

    filepath = os.path.join(DATA_DIR, filename)

    # Don't save full HTML to keep files manageable
    save_data = {}
    for name, data in results.items():
        save_data[name] = {
            "homepage": data["homepage"],
            "news_url": data.get("news_url"),
            "tier": data.get("tier"),
            "keywords": data.get("keywords", []),
            "crawled_at": data["crawled_at"],
            "keyword_alerts": data.get("keyword_alerts", []),
            "pages": [
                {
                    "url": p["url"],
                    "content_hash": p["content_hash"],
                    "text_content": p["text_content"][:5000],  # Truncate for storage
                    "fetched_at": p["fetched_at"],
                }
                for p in data["pages"]
            ],
            "pricing_page": (
                {
                    "url": data["pricing_page"]["url"],
                    "content_hash": data["pricing_page"]["content_hash"],
                    "text_content": data["pricing_page"]["text_content"],
                }
                if data["pricing_page"]
                else None
            ),
        }

    with open(filepath, "w") as f:
        json.dump(save_data, f, indent=2)

    print(f"\nSaved crawl data to {filepath}")
    return filepath


if __name__ == "__main__":
    print("Starting competitor crawl...")
    results = crawl_all_competitors()
    save_crawl_data(results)
    print("Done!")
