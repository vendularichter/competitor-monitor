"""
Visual change detection using screenshots.
Requires: playwright (pip install playwright && playwright install chromium)
"""

from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO

from config import COMPETITORS, SCREENSHOTS_DIR, VISUAL_CHANGE_THRESHOLD

# Optional imports - will work without them but screenshot features disabled
try:
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: playwright not installed. Screenshot features disabled.")
    print("Install with: pip install playwright && playwright install chromium")

try:
    from PIL import Image
    import imagehash

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: Pillow/imagehash not installed. Image comparison disabled.")
    print("Install with: pip install Pillow imagehash")


def ensure_screenshot_dir():
    """Create screenshots directory if it doesn't exist."""
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


def get_screenshot_filename(competitor_name: str, url: str, timestamp: str = None) -> str:
    """Generate a filename for a screenshot."""
    # Create safe filename from URL
    safe_name = competitor_name.replace(" ", "_").lower()
    url_hash = hash(url) % 10000

    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"{safe_name}_{url_hash}_{timestamp}.png"


def take_screenshot(url: str, output_path: str, full_page: bool = True) -> bool:
    """Take a screenshot of a URL using Playwright."""
    if not PLAYWRIGHT_AVAILABLE:
        print("Playwright not available. Skipping screenshot.")
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
            )
            page = context.new_page()

            # Navigate and wait for content
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait a bit more for any animations
            page.wait_for_timeout(2000)

            # Take screenshot
            page.screenshot(path=output_path, full_page=full_page)

            browser.close()
            return True

    except Exception as e:
        print(f"Error taking screenshot of {url}: {e}")
        return False


def compare_screenshots(image1_path: str, image2_path: str) -> dict:
    """Compare two screenshots and return similarity metrics."""
    if not PIL_AVAILABLE:
        return {"error": "PIL/imagehash not available", "similar": None}

    try:
        img1 = Image.open(image1_path)
        img2 = Image.open(image2_path)

        # Compute perceptual hashes
        hash1 = imagehash.phash(img1)
        hash2 = imagehash.phash(img2)

        # Hamming distance (0 = identical, higher = more different)
        hash_diff = hash1 - hash2

        # Also compute average hash for another perspective
        ahash1 = imagehash.average_hash(img1)
        ahash2 = imagehash.average_hash(img2)
        ahash_diff = ahash1 - ahash2

        # Convert to similarity percentage (assuming max diff of 64 for 8x8 hash)
        phash_similarity = max(0, 100 - (hash_diff / 64 * 100))
        ahash_similarity = max(0, 100 - (ahash_diff / 64 * 100))

        # Average of both methods
        avg_similarity = (phash_similarity + ahash_similarity) / 2

        return {
            "similar": avg_similarity >= (100 - VISUAL_CHANGE_THRESHOLD),
            "similarity_percent": round(avg_similarity, 1),
            "phash_diff": hash_diff,
            "ahash_diff": ahash_diff,
        }

    except Exception as e:
        return {"error": str(e), "similar": None}


def get_previous_screenshot(competitor_name: str, url: str) -> str | None:
    """Find the most recent screenshot for a competitor/URL."""
    if not os.path.exists(SCREENSHOTS_DIR):
        return None

    safe_name = competitor_name.replace(" ", "_").lower()
    url_hash = hash(url) % 10000
    prefix = f"{safe_name}_{url_hash}_"

    matching_files = [f for f in os.listdir(SCREENSHOTS_DIR) if f.startswith(prefix) and f.endswith(".png")]

    if not matching_files:
        return None

    # Sort by timestamp (embedded in filename) and get most recent
    matching_files.sort(reverse=True)
    return os.path.join(SCREENSHOTS_DIR, matching_files[0])


def take_competitor_screenshots() -> dict:
    """Take screenshots of all competitor homepages."""
    ensure_screenshot_dir()
    results = {}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for competitor in COMPETITORS:
        name = competitor["name"]
        homepage = competitor["homepage"]

        print(f"Taking screenshot of {name}...")

        filename = get_screenshot_filename(name, homepage, timestamp)
        filepath = os.path.join(SCREENSHOTS_DIR, filename)

        success = take_screenshot(homepage, filepath)

        if success:
            # Compare with previous screenshot
            prev_screenshot = get_previous_screenshot(name, homepage)
            comparison = None

            if prev_screenshot and prev_screenshot != filepath:
                print(f"  Comparing with previous screenshot...")
                comparison = compare_screenshots(prev_screenshot, filepath)

            results[name] = {
                "url": homepage,
                "screenshot_path": filepath,
                "previous_screenshot": prev_screenshot,
                "comparison": comparison,
                "timestamp": timestamp,
            }
        else:
            results[name] = {
                "url": homepage,
                "error": "Failed to take screenshot",
                "timestamp": timestamp,
            }

    return results


def generate_visual_report(results: dict) -> str:
    """Generate a report of visual changes."""
    report_lines = ["# Visual Changes Report", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

    significant_changes = []

    for name, data in results.items():
        if data.get("error"):
            report_lines.append(f"## {name}")
            report_lines.append(f"  Error: {data['error']}")
            continue

        comparison = data.get("comparison")
        if comparison and not comparison.get("error"):
            if not comparison["similar"]:
                significant_changes.append(
                    {
                        "name": name,
                        "url": data["url"],
                        "similarity": comparison["similarity_percent"],
                    }
                )

    if significant_changes:
        report_lines.append("## Significant Visual Changes Detected")
        report_lines.append("")
        for change in significant_changes:
            report_lines.append(f"### {change['name']}")
            report_lines.append(f"- URL: {change['url']}")
            report_lines.append(f"- Similarity: {change['similarity']}% (threshold: {100 - VISUAL_CHANGE_THRESHOLD}%)")
            report_lines.append("")
    else:
        report_lines.append("No significant visual changes detected.")

    return "\n".join(report_lines)


if __name__ == "__main__":
    if not PLAYWRIGHT_AVAILABLE:
        print("\nTo enable screenshot monitoring, install playwright:")
        print("  pip install playwright")
        print("  playwright install chromium")
    else:
        print("Taking competitor screenshots...")
        results = take_competitor_screenshots()
        report = generate_visual_report(results)
        print("\n" + report)
