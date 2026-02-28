# Competitor Monitor

A tool to monitor competitor websites for changes and send weekly updates to Slack.

## Features

- **Website Crawling**: Automatically discovers and crawls pages on competitor sites
- **Content Change Detection**: Detects text changes, new pages, removed pages
- **Pricing Monitoring**: Specifically tracks pricing page changes
- **Visual Comparison**: Takes screenshots and detects visual/design changes
- **Slack Notifications**: Sends formatted reports to your Slack channel

## Quick Start

### 1. Install Dependencies

```bash
cd competitor-monitor
pip install -r requirements.txt

# For screenshot features (optional but recommended):
playwright install chromium
```

### 2. Configure Competitors

Edit `config.py` and add your competitors:

```python
COMPETITORS = [
    {
        "name": "Acme Corp",
        "homepage": "https://acme.com",
        "pricing_url": "https://acme.com/pricing",  # Optional
    },
    {
        "name": "Widget Inc",
        "homepage": "https://widget.io",
        "pricing_url": None,  # Will auto-detect
    },
]
```

### 3. Set Up Slack Webhook

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name it "Competitor Monitor" and select your workspace
4. Go to "Incoming Webhooks" → Enable it
5. Click "Add New Webhook to Workspace"
6. Select the channel for notifications
7. Copy the webhook URL
8. Paste it in `config.py`:

```python
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### 4. Run Your First Scan

```bash
# First run (creates baseline):
python monitor.py --dry-run

# Check it worked:
ls data/  # Should see a crawl_*.json file
```

### 5. Set Up Weekly Schedule

#### macOS (using launchd):

```bash
# Create the plist file
cat > ~/Library/LaunchAgents/com.competitor-monitor.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.competitor-monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/vendularichter/claude/competitor-monitor/monitor.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>1</integer>  <!-- Monday -->
        <key>Hour</key>
        <integer>9</integer>  <!-- 9 AM -->
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/vendularichter/claude/competitor-monitor/logs/monitor.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/vendularichter/claude/competitor-monitor/logs/monitor.log</string>
</dict>
</plist>
EOF

# Load it
launchctl load ~/Library/LaunchAgents/com.competitor-monitor.plist
```

#### Alternative: Using cron

```bash
# Edit crontab
crontab -e

# Add this line (runs every Monday at 9 AM):
0 9 * * 1 cd /Users/vendularichter/claude/competitor-monitor && /usr/bin/python3 monitor.py >> logs/cron.log 2>&1
```

## Usage

```bash
# Full monitoring run
python monitor.py

# Skip screenshots (faster)
python monitor.py --no-screenshots

# Test run without Slack
python monitor.py --dry-run

# Just crawl, no comparison
python monitor.py --crawl-only
```

## Configuration Options

Edit `config.py` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_PAGES_PER_SITE` | 50 | Max pages to crawl per site |
| `MAX_CRAWL_DEPTH` | 2 | How deep to follow links |
| `REQUEST_DELAY` | 1.0 | Seconds between requests |
| `CONTENT_CHANGE_THRESHOLD` | 5 | % change to trigger alert |
| `VISUAL_CHANGE_THRESHOLD` | 10 | Visual diff sensitivity |

## Troubleshooting

**"playwright not installed"**
```bash
pip install playwright
playwright install chromium
```

**"No previous data to compare"**
This is normal on first run. Run again after a few days to see changes.

**"Slack webhook not configured"**
Add your webhook URL to `config.py`. See setup instructions above.

**Crawl taking too long**
Reduce `MAX_PAGES_PER_SITE` or `MAX_CRAWL_DEPTH` in config.py
