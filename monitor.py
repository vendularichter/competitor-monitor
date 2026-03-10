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
from media_scanner import generate_media_report, get_latest_media_scans, get_new_mentions, get_never_notified_mentions, load_media_scan, save_media_scan, save_notified_articles, scan_all_media
from screenshot_monitor import generate_visual_report, take_competitor_screenshots
from slack_notifier import send_competitor_report, send_error_notification


def run_full_monitor(skip_screenshots: bool = False, skip_media: bool = False, dry_run: bool = False):
    """Run the complete monitoring process."""
    print(f"=" * 60)
    print(f"Competitor Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"=" * 60)

    try:
        # Step 1: Crawl all competitor websites
        print("\n[1/4] Crawling competitor websites...")
        crawl_results = crawl_all_competitors()
        crawl_file = save_crawl_data(crawl_results)

        # Step 2: Compare with previous crawl
        print("\n[2/4] Detecting content changes...")
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
        updated_notified_urls = set()
        if not skip_media:
            print("\n[3/4] Scanning media sources for competitor mentions...")
            media_results = scan_all_media()
            save_media_scan(media_results)

            # Get only articles that have NEVER been notified before
            media_mentions, updated_notified_urls = get_never_notified_mentions(media_results)

            total_new = sum(len(d["articles"]) for d in media_mentions.values())
            if total_new:
                print(f"\n  Found {total_new} NEW article mentions (never notified before)!")
                print(generate_media_report(media_results, media_mentions))
            else:
                print("\n  No NEW mentions (all articles previously notified)")
        else:
            print("\n[3/4] Media scan skipped (--no-media flag)")

        # Step 4: Send Slack notification
        print("\n[4/4] Sending Slack notification...")
        if dry_run:
            print("  Dry run - not sending to Slack")
            print("  Would send report with:")
            print(f"    - {len(changes)} competitors with content changes")
            print(f"    - {sum(len(d['articles']) for d in media_mentions.values())} media mentions")
        else:
            # Always send combined report (shows "No update" sections if empty)
            success = send_competitor_report(changes, None, None, media_mentions)
            if success:
                # Save notified articles only after successful Slack send
                if updated_notified_urls:
                    save_notified_articles(updated_notified_urls)
                    print("  Sent successfully and recorded notified articles!")
                else:
                    print("  Sent successfully!")
            else:
                print("  Failed to send (check webhook URL) - will retry next run")

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

        # Get only articles that have NEVER been notified before
        media_mentions, updated_notified_urls = get_never_notified_mentions(results)

        total_new = sum(len(d["articles"]) for d in media_mentions.values())
        print(f"\n{total_new} NEW article mentions (never notified before)")
        if total_new:
            print(generate_media_report(results, media_mentions))

        # Always send to Slack (shows "No update" if empty)
        print("\nSending media report to Slack...")
        success = send_competitor_report({}, None, None, media_mentions, is_media_report=True)
        if success:
            if updated_notified_urls:
                save_notified_articles(updated_notified_urls)
                print("Sent and recorded notified articles!")
            else:
                print("Sent!")
        else:
            print("Failed to send - will retry next run")
    else:
        run_full_monitor(
            skip_screenshots=args.no_screenshots,
            skip_media=args.no_media,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    main()
