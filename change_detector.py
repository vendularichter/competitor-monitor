"""
Detects changes between crawl snapshots.
"""

from __future__ import annotations

import difflib
import json
import os
import re
from datetime import datetime
from typing import Optional

from config import CONTENT_CHANGE_THRESHOLD, DATA_DIR


def get_latest_crawls(count: int = 2) -> list[str]:
    """Get the most recent crawl files."""
    if not os.path.exists(DATA_DIR):
        return []

    files = [f for f in os.listdir(DATA_DIR) if f.startswith("crawl_") and f.endswith(".json")]
    files.sort(reverse=True)
    return [os.path.join(DATA_DIR, f) for f in files[:count]]


def load_crawl_data(filepath: str) -> dict:
    """Load crawl data from JSON file."""
    with open(filepath) as f:
        return json.load(f)


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity ratio between two texts (0-100)."""
    if not text1 and not text2:
        return 100.0
    if not text1 or not text2:
        return 0.0

    # Use difflib for similarity
    ratio = difflib.SequenceMatcher(None, text1, text2).ratio()
    return ratio * 100


def get_text_diff(text1: str, text2: str, context_lines: int = 3) -> list[str]:
    """Get human-readable diff between two texts."""
    lines1 = text1.split(". ")
    lines2 = text2.split(". ")

    diff = difflib.unified_diff(lines1, lines2, lineterm="", n=context_lines)
    return list(diff)


def extract_key_changes(old_text: str, new_text: str) -> dict:
    """Extract meaningful changes between texts."""
    changes = {
        "added_phrases": [],
        "removed_phrases": [],
        "price_changes": [],
    }

    # Simple word-level diff
    old_words = set(old_text.lower().split())
    new_words = set(new_text.lower().split())

    added = new_words - old_words
    removed = old_words - new_words

    # Look for significant additions (filter out common words)
    common_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "is",
        "are",
        "was",
        "were",
    }
    significant_added = [w for w in added if w not in common_words and len(w) > 3]
    significant_removed = [w for w in removed if w not in common_words and len(w) > 3]

    changes["added_phrases"] = significant_added[:20]  # Limit to 20
    changes["removed_phrases"] = significant_removed[:20]

    # Look for price changes
    price_pattern = r"\$[\d,]+(?:\.\d{2})?|\d+(?:\.\d{2})?\s*(?:USD|EUR|GBP)"
    old_prices = set(re.findall(price_pattern, old_text, re.I))
    new_prices = set(re.findall(price_pattern, new_text, re.I))

    if old_prices != new_prices:
        changes["price_changes"] = {
            "old_prices": list(old_prices),
            "new_prices": list(new_prices),
        }

    return changes


def compare_pages(old_pages: list[dict], new_pages: list[dict]) -> list[dict]:
    """Compare two sets of pages and return changes."""
    changes = []

    # Create lookup by URL
    old_by_url = {p["url"]: p for p in old_pages}
    new_by_url = {p["url"]: p for p in new_pages}

    # Find new pages
    for url in new_by_url:
        if url not in old_by_url:
            changes.append(
                {
                    "type": "new_page",
                    "url": url,
                    "summary": f"New page discovered: {url}",
                }
            )

    # Find removed pages
    for url in old_by_url:
        if url not in new_by_url:
            changes.append(
                {
                    "type": "removed_page",
                    "url": url,
                    "summary": f"Page no longer accessible: {url}",
                }
            )

    # Find changed pages
    for url in old_by_url:
        if url in new_by_url:
            old_page = old_by_url[url]
            new_page = new_by_url[url]

            # Quick check using hash
            if old_page["content_hash"] != new_page["content_hash"]:
                similarity = calculate_text_similarity(
                    old_page["text_content"], new_page["text_content"]
                )
                change_percent = 100 - similarity

                if change_percent >= CONTENT_CHANGE_THRESHOLD:
                    key_changes = extract_key_changes(
                        old_page["text_content"], new_page["text_content"]
                    )

                    changes.append(
                        {
                            "type": "content_changed",
                            "url": url,
                            "change_percent": round(change_percent, 1),
                            "key_changes": key_changes,
                            "summary": f"Page changed by {change_percent:.1f}%: {url}",
                        }
                    )

    return changes


def compare_pricing(old_pricing: dict | None, new_pricing: dict | None) -> dict | None:
    """Compare pricing pages specifically."""
    if not old_pricing and not new_pricing:
        return None

    if not old_pricing and new_pricing:
        return {
            "type": "pricing_added",
            "url": new_pricing["url"],
            "summary": "Pricing page detected for the first time",
        }

    if old_pricing and not new_pricing:
        return {
            "type": "pricing_removed",
            "url": old_pricing["url"],
            "summary": "Pricing page no longer accessible",
        }

    if old_pricing["content_hash"] != new_pricing["content_hash"]:
        key_changes = extract_key_changes(old_pricing["text_content"], new_pricing["text_content"])

        if key_changes.get("price_changes"):
            return {
                "type": "pricing_changed",
                "url": new_pricing["url"],
                "price_changes": key_changes["price_changes"],
                "summary": "Pricing has been updated",
            }
        else:
            return {
                "type": "pricing_page_updated",
                "url": new_pricing["url"],
                "summary": "Pricing page content changed (no price changes detected)",
            }

    return None


def detect_all_changes(old_data: dict, new_data: dict) -> dict:
    """Detect all changes between two crawl snapshots."""
    all_changes = {}

    for competitor_name in new_data:
        if competitor_name not in old_data:
            all_changes[competitor_name] = {
                "summary": "New competitor added to monitoring",
                "page_changes": [],
                "pricing_changes": None,
            }
            continue

        old_competitor = old_data[competitor_name]
        new_competitor = new_data[competitor_name]

        page_changes = compare_pages(old_competitor["pages"], new_competitor["pages"])

        pricing_changes = compare_pricing(
            old_competitor.get("pricing_page"), new_competitor.get("pricing_page")
        )

        if page_changes or pricing_changes:
            all_changes[competitor_name] = {
                "page_changes": page_changes,
                "pricing_changes": pricing_changes,
                "total_changes": len(page_changes) + (1 if pricing_changes else 0),
            }

    return all_changes


def generate_change_report(changes: dict) -> str:
    """Generate a human-readable change report."""
    if not changes:
        return "No significant changes detected across all competitors."

    report_lines = ["# Competitor Changes Report", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

    for competitor, data in changes.items():
        report_lines.append(f"## {competitor}")
        report_lines.append("")

        # Pricing changes (most important)
        if data.get("pricing_changes"):
            pc = data["pricing_changes"]
            report_lines.append(f"### 💰 Pricing: {pc['summary']}")
            if pc.get("price_changes"):
                report_lines.append(f"  - Old prices: {', '.join(pc['price_changes']['old_prices'])}")
                report_lines.append(f"  - New prices: {', '.join(pc['price_changes']['new_prices'])}")
            report_lines.append("")

        # Page changes
        if data.get("page_changes"):
            report_lines.append(f"### 📄 Page Changes ({len(data['page_changes'])} pages)")
            for change in data["page_changes"][:10]:  # Limit to 10
                report_lines.append(f"  - {change['summary']}")
                if change.get("key_changes", {}).get("added_phrases"):
                    added = ", ".join(change["key_changes"]["added_phrases"][:5])
                    report_lines.append(f"    Added: {added}")
            report_lines.append("")

    return "\n".join(report_lines)


if __name__ == "__main__":
    crawls = get_latest_crawls(2)
    if len(crawls) < 2:
        print("Need at least 2 crawl snapshots to compare. Run crawler.py first, then again later.")
    else:
        print(f"Comparing {crawls[1]} vs {crawls[0]}")
        old_data = load_crawl_data(crawls[1])  # Older
        new_data = load_crawl_data(crawls[0])  # Newer

        changes = detect_all_changes(old_data, new_data)
        report = generate_change_report(changes)
        print(report)
