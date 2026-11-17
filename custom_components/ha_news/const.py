"""Constants for News."""

from datetime import timedelta

DOMAIN = "ha_news"
PLATFORMS = ["sensor"]

CONF_PREFIX = "prefix"  # an emoji shown before the source, e.g. 🇮🇪
CONF_ITEMS = "items"  # how many headlines to keep

DEFAULT_ITEMS = 5
MAX_ITEMS = 20
SCAN_INTERVAL = timedelta(minutes=30)
TIMEOUT = 30  # seconds

STATIC_URL = "/ha_news_static"
CARDS = ("news-ticker-card.js", "news-feed-card.js")
