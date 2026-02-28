"""
Slack integration for sending competitor monitoring alerts.
"""

import json

import requests

from config import SLACK_WEBHOOK_URL


def send_slack_message(message: str, blocks: list = None) -> bool:
    """Send a message to Slack via webhook."""
    if SLACK_WEBHOOK_URL == "YOUR_SLACK_WEBHOOK_URL_HERE":
        print("Slack webhook not configured. Set SLACK_WEBHOOK_URL in config.py")
        print(f"Would have sent: {message[:200]}...")
        return False

    payload = {"text": message}

    if blocks:
        payload["blocks"] = blocks

    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Error sending Slack message: {e}")
        return False


def format_changes_for_slack(changes: dict, visual_results: dict = None, keyword_alerts: dict = None, media_mentions: dict = None) -> tuple[str, list]:
    """Format change data into Slack blocks."""
    from datetime import datetime
    date_str = datetime.now().strftime("%b %d, %Y")

    has_content = changes or visual_results or keyword_alerts or media_mentions

    # Check if this is media-only (no competitor data)
    is_media_only = media_mentions and not changes and not visual_results and not keyword_alerts

    if not has_content:
        if is_media_only:
            text = "Media Monitor: No new mentions this week."
            header = f"📰 Media Monitor - {date_str}"
        else:
            text = "Competitor Monitor: No significant changes detected this week."
            header = f"🔍 Competitor Monitor - {date_str}"
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": header, "emoji": True},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "No significant changes detected."},
            },
        ]
        return text, blocks

    # Choose emoji and header based on content type
    if is_media_only:
        text = "📰 Media Monitor: New mentions found!"
        header = f"📰 Media Monitor - {date_str}"
    else:
        text = "🔍 Competitor Monitor: Changes detected!"
        header = f"🔍 Competitor Monitor - {date_str}"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header, "emoji": True},
        },
    ]

    # HIGH-ALERT: Keyword alerts (most important!)
    if keyword_alerts:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "🚨 *HIGH-ALERT KEYWORDS DETECTED*"},
            }
        )
        for competitor, alerts in keyword_alerts.items():
            tier = alerts.get("tier", "")
            tier_prefix = f"[{tier}] " if tier else ""
            for alert in alerts.get("alerts", [])[:3]:  # Top 3 alerts per competitor
                keywords_found = ", ".join([m["keyword"] for m in alert["matches"]])
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{tier_prefix}{competitor}*: `{keywords_found}`\n<{alert['url']}|View page>",
                        },
                    }
                )
        blocks.append({"type": "divider"})

    # Content/pricing changes
    for competitor, data in changes.items():
        tier = data.get("tier", "")
        tier_prefix = f"[{tier}] " if tier else ""

        # Pricing changes (highlight these!)
        if data.get("pricing_changes"):
            pc = data["pricing_changes"]
            pricing_text = f"*{tier_prefix}{competitor}* - {pc['summary']}"

            if pc.get("price_changes"):
                old = ", ".join(pc["price_changes"]["old_prices"][:5])
                new = ", ".join(pc["price_changes"]["new_prices"][:5])
                pricing_text += f"\n> Old: {old}\n> New: {new}"

            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": pricing_text},
                }
            )

        # Page changes
        page_changes = data.get("page_changes", [])
        if page_changes:
            # Group by type
            new_pages = [c for c in page_changes if c["type"] == "new_page"]
            changed_pages = [c for c in page_changes if c["type"] == "content_changed"]
            removed_pages = [c for c in page_changes if c["type"] == "removed_page"]

            summary_parts = []
            if new_pages:
                summary_parts.append(f"{len(new_pages)} new pages")
            if changed_pages:
                summary_parts.append(f"{len(changed_pages)} changed pages")
            if removed_pages:
                summary_parts.append(f"{len(removed_pages)} removed pages")

            page_text = f"*{tier_prefix}{competitor}* - {', '.join(summary_parts)}"

            # Add details for most significant changes
            details = []
            for change in changed_pages[:3]:  # Top 3 changed pages
                details.append(f"• <{change['url']}|Page> changed by {change.get('change_percent', '?')}%")

            for change in new_pages[:2]:  # Top 2 new pages
                details.append(f"• New: <{change['url']}|{change['url'][:50]}...>")

            if details:
                page_text += "\n" + "\n".join(details)

            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": page_text},
                }
            )

        blocks.append({"type": "divider"})

    # Media mentions (new article format)
    if media_mentions:
        total_articles = sum(len(d.get("articles", [])) for d in media_mentions.values())
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"📰 *NEW MEDIA MENTIONS* ({total_articles} articles)"},
            }
        )

        for source_name, data in media_mentions.items():
            category = data.get("category", "")
            articles = data.get("articles", [])[:5]  # Top 5 per source

            if articles:
                # Group articles for this source
                article_lines = []
                for article in articles:
                    terms = ", ".join(article.get("terms", []))
                    title = article.get("title", "Article")[:50]
                    url = article.get("url", "")
                    article_lines.append(f"• <{url}|{title}...>\n  _Mentions: {terms}_")

                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{source_name}* ({category}):\n" + "\n".join(article_lines),
                        },
                    }
                )

        blocks.append({"type": "divider"})

    # Visual changes
    if visual_results:
        visual_changes = []
        for name, data in visual_results.items():
            comparison = data.get("comparison", {})
            if comparison and not comparison.get("error") and not comparison.get("similar"):
                visual_changes.append(
                    {
                        "name": name,
                        "similarity": comparison["similarity_percent"],
                        "url": data["url"],
                    }
                )

        if visual_changes:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "👁️ *Visual Changes Detected*"},
                }
            )

            for vc in visual_changes:
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"• *{vc['name']}* homepage looks {vc['similarity']:.0f}% similar to before",
                        },
                    }
                )

    return text, blocks


def send_competitor_report(changes: dict, visual_results: dict = None, keyword_alerts: dict = None, media_mentions: dict = None) -> bool:
    """Send the full competitor report to Slack."""
    text, blocks = format_changes_for_slack(changes, visual_results, keyword_alerts, media_mentions)
    return send_slack_message(text, blocks)


def send_error_notification(error_message: str) -> bool:
    """Send an error notification to Slack."""
    text = f"Competitor Monitor Error: {error_message}"
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Competitor Monitor Error", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"```{error_message}```"},
        },
    ]
    return send_slack_message(text, blocks)


if __name__ == "__main__":
    # Test message
    test_changes = {
        "Example Competitor": {
            "pricing_changes": {
                "summary": "Pricing updated",
                "price_changes": {"old_prices": ["$99/mo"], "new_prices": ["$149/mo"]},
            },
            "page_changes": [
                {"type": "new_page", "url": "https://example.com/new-feature", "summary": "New page"},
                {
                    "type": "content_changed",
                    "url": "https://example.com/about",
                    "change_percent": 15.5,
                    "summary": "About page changed",
                },
            ],
        }
    }

    print("Sending test message to Slack...")
    success = send_competitor_report(test_changes)
    print(f"Result: {'Success' if success else 'Failed (check webhook URL)'}")
