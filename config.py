"""
Configuration for competitor monitoring tool.
Edit COMPETITORS list with your competitor URLs.
"""

# ============================================
# COMPETITOR WEBSITES TO MONITOR
# Add your competitor homepage URLs here
# ============================================
COMPETITORS = [
    # Tier 1: Full-Stack
    {
        "name": "BETER",
        "homepage": "https://beter.co",
        "news_url": "https://beter.co/news/",
        "pricing_url": None,
        "tier": "Tier 1",
    },
    # Tier 1: Tech-First
    {
        "name": "DATA.BET",
        "homepage": "https://data.bet",
        "news_url": "https://data.bet/news/",
        "pricing_url": None,
        "tier": "Tier 1",
    },
    # Tier 1: Data-First
    {
        "name": "PandaScore",
        "homepage": "https://pandascore.co",
        "news_url": "https://pandascore.co/blog/",
        "pricing_url": None,
        "tier": "Tier 1",
    },
    # Tier 2: Rights/Data
    {
        "name": "GRID",
        "homepage": "https://grid.gg",
        "news_url": "https://grid.gg/newsroom/",
        "pricing_url": None,
        "tier": "Tier 2",
    },
    # Tier 2: eSims
    {
        "name": "SIS.tv",
        "homepage": "https://sis.tv",
        "news_url": "https://sis.tv/category/news-press/",
        "pricing_url": None,
        "tier": "Tier 2",
    },
    # Tier 3: Goliaths
    {
        "name": "Sportradar",
        "homepage": "https://sportradar.com",
        "news_url": "https://sportradar.com/news-archive/",
        "pricing_url": None,
        "tier": "Tier 3",
    },
    # Tier 3: Platforms
    {
        "name": "Betconstruct",
        "homepage": "https://betconstruct.com",
        "news_url": "https://betconstruct.com/news/",
        "pricing_url": None,
        "tier": "Tier 3",
    },
]

# ============================================
# MEDIA SOURCES TO MONITOR
# Scan these for mentions of competitors
# ============================================
MEDIA_SOURCES = [
    # Your requested sources
    {
        "name": "EGR Global",
        "url": "https://egr.global/intel/",
        "category": "Industry News",
    },
    {
        "name": "SBC News",
        "url": "https://sbcnews.co.uk/",
        "category": "Industry News",
    },
    {
        "name": "iGB (iGaming Business)",
        "url": "https://igamingbusiness.com/",
        "category": "Industry News",
    },
    # NEXT.io removed - aggressive bot protection blocks all automated access
    {
        "name": "Revista Casino Peru",
        "url": "https://revistacasinoperu.com/c/reportes/noticias-reportes/",
        "category": "LatAm",
    },
    {
        "name": "Esports Insider",  # Alternative to Esports Radar (SSL issues)
        "url": "https://esportsinsider.com/",
        "category": "Esports",
    },
    {
        "name": "iGamingFuture",
        "url": "https://igamingfuture.com/",
        "category": "Industry News",
    },
    # Additional suggested sources
    {
        "name": "Esports.net",
        "url": "https://www.esports.net/news/",
        "category": "Esports",
    },
    {
        "name": "Yogonet",
        "url": "https://www.yogonet.com/international/",
        "category": "LatAm/Global",
    },
]

# Terms to search for in media (competitor names + your keywords)
MEDIA_SEARCH_TERMS = [
    # Competitor names
    "BETER",
    "DATA.BET",
    "PandaScore",
    "GRID",
    "Bayes Esports",
    "SIS",
    "Sportradar",
    "Betconstruct",
    # Your product keywords
    "esports betting",
    "esports odds",
    "esports data",
    "eSims",
    "eFootball",
    "eBasketball",
    "Bet Builder",
    "iFrame betting",
]

# ============================================
# SLACK CONFIGURATION
# ============================================
# Get this from: https://api.slack.com/messaging/webhooks
# Set SLACK_WEBHOOK_URL environment variable or GitHub secret
import os
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "YOUR_SLACK_WEBHOOK_URL_HERE")

# ============================================
# CRAWLING SETTINGS
# ============================================
# Maximum pages to crawl per website (to avoid crawling forever)
MAX_PAGES_PER_SITE = 50

# Maximum depth of links to follow (1 = homepage only, 2 = homepage + linked pages, etc.)
MAX_CRAWL_DEPTH = 2

# Delay between requests in seconds (be polite to servers)
REQUEST_DELAY = 1.0

# User agent string
USER_AGENT = "CompetitorMonitor/1.0 (Internal Business Tool)"

# ============================================
# CHANGE DETECTION SETTINGS
# ============================================
# Minimum percentage of content change to report (0-100)
# Lower = more sensitive, Higher = only major changes
CONTENT_CHANGE_THRESHOLD = 5  # 5% change triggers alert

# Screenshot comparison sensitivity (0-100)
# Lower = more sensitive to visual changes
VISUAL_CHANGE_THRESHOLD = 10

# ============================================
# FILE PATHS (relative to project root)
# ============================================
DATA_DIR = "data"
SCREENSHOTS_DIR = "screenshots"
LOGS_DIR = "logs"
