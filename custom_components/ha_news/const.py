"""Constants for News."""

from datetime import timedelta

DOMAIN = "ha_news"
PLATFORMS = ["sensor"]

CONF_PREFIX = "prefix"  # an emoji shown before the source, e.g. 🇮🇪
CONF_ITEMS = "items"  # how many headlines to keep
CONF_INCLUDE = "include"  # keep only headlines with one of these words
CONF_EXCLUDE = "exclude"  # drop headlines with any of these words

# Google News search feeds: entry.data[CONF_SOURCE] = SOURCE_GOOGLE, and
# the search in options (the address is built from it).
CONF_SOURCE = "source"
SOURCE_GOOGLE = "google"
CONF_QUERY = "query"
CONF_EDITION = "edition"
CONF_WHEN = "when"
MAX_QUERY = 300  # characters

DEFAULT_ITEMS = 5
MAX_ITEMS = 20
SCAN_INTERVAL = timedelta(minutes=30)
TIMEOUT = 30  # seconds

STATIC_URL = "/ha_news_static"
CARDS = ("news-ticker-card.js", "news-feed-card.js")
