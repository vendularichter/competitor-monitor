#!/usr/bin/env python3
"""
Main script to run competitor monitoring.
Run this weekly via cron or manually.
"""

import argparse
import sys
import traceback
from datetime import datetime

from change_detector import detect_all_changes, generate_change_report, get_latest_crawls, load_crawl_data
from crawler import crawl_all_competitors, save_crawl_data
from media_scanner import generate_media_report, get_latest_media_scans, get_new_mentions, load_media_scan, save_media_scan, scan_all_media
from screenshot_monitor import generate_visual_report, take_competitor_screenshots
from slack_notifier import send_competitor_report, send_error_notification


def run_full_monitor(skip_screenshots: bool = False, skip_media: bool = False, dry_run: bool = False):
    """Run the complete monitoring process."""
    print(f"=" * 60)
    print(f"Competitor Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"=" * 60)

    try:
        # Step 1: Crawl all competitor websites
        print("\n[1/5] Crawling competitor websites...")
        crawl_results = crawl_all_competitors()
        crawl_file = save_crawl_data(crawl_results)

        # Extract keyword alerts from crawl results
        keyword_alerts = {}
        for name, data in crawl_results.items():
            if data.get("keyword_alerts"):
                keyword_alerts[name] = {
                    "tier": data.get("tier"),
                    "alerts": data["keyword_alerts"]
                }

        if keyword_alerts:
            print(f"\n  HIGH-ALERT: Keywords found in {len(keyword_alerts)} competitors!")

        # Step 2: Compare with previous crawl
        print("\n[2/5] Detecting content changes...")
        crawl_files = get_latest_crawls(2)
        changes = {}

        if len(crawl_files) >= 2:
            old_data = load_crawl_data(crawl_files[1])
            new_data = load_crawl_data(crawl_files[0])
            changes = detect_all_changes(old_data, new_data)
            print(generate_change_report(changes))
        else:
            print("  First run - no previous data to compare. Run again later to detect changes.")

        # Step 3: Scan media sources for competitor mentions
        media_mentions = {}
        if not skip_media:
            print("\n[3/5] Scanning media sources for competitor mentions...")
            media_results = scan_all_media()
            save_media_scan(media_results)

            # Check for week-over-week changes (only show NEW mentions)
            media_scan_files = get_latest_media_scans(2)
            if len(media_scan_files) >= 2:
                previous_scan = load_media_scan(media_scan_files[1])
                new_mentions = get_new_mentions(media_results, previous_scan)
                media_mentions = new_mentions

                total_new = sum(len(d["articles"]) for d in new_mentions.values())
                if total_new:
                    print(f"\n  Found {total_new} NEW article mentions this week!")
                    print(generate_media_report(media_results, new_mentions))
                else:
                    print("\n  No NEW mentions this week (all seen before)")
            else:
                # First run - show all mentions
                for source_name, data in media_results.items():
                    articles = data.get("articles_with_mentions", [])
                    if articles:
                        media_mentions[source_name] = {
                            "category": data.get("category", ""),
                            "articles": articles
                        }

                if media_mentions:
                    total = sum(len(d["articles"]) for d in media_mentions.values())
                    print(f"\n  Found {total} article mentions!")
                    print(generate_media_report(media_results))
        else:
            print("\n[3/5] Media scan skipped (--no-media flag)")

        # Step 4: Take and compare screenshots
        visual_results = {}
        if not skip_screenshots:
            print("\n[4/5] Taking screenshots and comparing...")
            visual_results = take_competitor_screenshots()
            print(generate_visual_report(visual_results))
        else:
            print("\n[4/5] Screenshots skipped (--no-screenshots flag)")

        # Step 5: Send Slack notification
        print("\n[5/5] Sending Slack notification...")
        if dry_run:
            print("  Dry run - not sending to Slack")
            print("  Would send report with:")
            print(f"    - {len(keyword_alerts)} competitors with keyword alerts")
            print(f"    - {len(changes)} competitors with content changes")
            print(f"    - {len(media_mentions)} media sources with mentions")
            print(f"    - {len(visual_results)} visual comparisons")
        else:
            has_changes = bool(changes) or bool(keyword_alerts) or bool(media_mentions) or any(
                r.get("comparison", {}).get("similar") is False for r in visual_results.values()
            )

            if has_changes or len(crawl_files) < 2:
                success = send_competitor_report(changes, visual_results, keyword_alerts, media_mentions)
                print(f"  {'Sent successfully!' if success else 'Failed to send (check webhook URL)'}")
            else:
                print("  No significant changes - skipping Slack notification")

        print("\n" + "=" * 60)
        print("Monitoring complete!")
        print("=" * 60)

    except Exception as e:
        error_msg = f"Error during monitoring: {str(e)}\n{traceback.format_exc()}"
        print(f"\nERROR: {error_msg}")

        if not dry_run:
            send_error_notification(error_msg)

        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Competitor Website Monitor")

    parser.add_argument(
        "--no-screenshots",
        action="store_true",
        help="Skip screenshot capture (faster, but no visual comparison)",
    )

    parser.add_argument(
        "--no-media",
        action="store_true",
        help="Skip media source scanning",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without sending Slack notifications",
    )

    parser.add_argument(
        "--crawl-only",
        action="store_true",
        help="Only crawl websites, don't compare or notify",
    )

    parser.add_argument(
        "--media-only",
        action="store_true",
        help="Only scan media sources, don't crawl competitors",
    )

    args = parser.parse_args()

    if args.crawl_only:
        print("Running crawl only...")
        results = crawl_all_competitors()
        save_crawl_data(results)
    elif args.media_only:
        print("Running media scan only...")
        results = scan_all_media()
        save_media_scan(results)

        # Check for week-over-week changes
        media_scan_files = get_latest_media_scans(2)
        media_mentions = {}

        if len(media_scan_files) >= 2:
            previous_scan = load_media_scan(media_scan_files[1])
            new_mentions = get_new_mentions(results, previous_scan)
            media_mentions = new_mentions

            total_new = sum(len(d["articles"]) for d in new_mentions.values())
            print(f"\n{total_new} NEW article mentions this week")
            print(generate_media_report(results, new_mentions))
        else:
            # First run - show all mentions
            for source_name, data in results.items():
                articles = data.get("articles_with_mentions", [])
                if articles:
                    media_mentions[source_name] = {
                        "category": data.get("category", ""),
                        "articles": articles
                    }
            print("\n" + generate_media_report(results))

        # Send to Slack
        if media_mentions:
            print("\nSending media report to Slack...")
            success = send_competitor_report({}, None, None, media_mentions)
            print(f"{'Sent!' if success else 'Failed to send'}")
        else:
            print("\nNo new mentions to send to Slack")
    else:
        run_full_monitor(
            skip_screenshots=args.no_screenshots,
            skip_media=args.no_media,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    main()
