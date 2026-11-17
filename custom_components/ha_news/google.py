"""Google News search feeds: build the RSS address from a search.

Google News has no documented API; its RSS search
(news.google.com/rss/search) is public, needs no key and has been stable
for years. If Google changes it, only these feeds break.
"""

from __future__ import annotations

from urllib.parse import urlencode

SEARCH_URL = "https://news.google.com/rss/search"

# Edition id (Google's ceid) -> (label, hl). gl is the part before ":".
# Labels in the edition's own language, sorted by label in the list.
EDITIONS: dict[str, tuple[str, str]] = {
    "AR:es-419": ("Argentina (Español)", "es-419"),
    "AU:en": ("Australia (English)", "en-AU"),
    "AT:de": ("Österreich (Deutsch)", "de"),
    "BE:fr": ("Belgique (Français)", "fr"),
    "BE:nl": ("België (Nederlands)", "nl"),
    "BR:pt-419": ("Brasil (Português)", "pt-BR"),
    "CA:en": ("Canada (English)", "en-CA"),
    "CA:fr": ("Canada (Français)", "fr-CA"),
    "CH:de": ("Schweiz (Deutsch)", "de"),
    "CH:fr": ("Suisse (Français)", "fr"),
    "CL:es-419": ("Chile (Español)", "es-419"),
    "CO:es-419": ("Colombia (Español)", "es-419"),
    "CZ:cs": ("Česko (Čeština)", "cs"),
    "DE:de": ("Deutschland (Deutsch)", "de"),
    "ES:es": ("España (Español)", "es"),
    "FR:fr": ("France (Français)", "fr"),
    "GB:en": ("United Kingdom (English)", "en-GB"),
    "GR:el": ("Ελλάδα (Ελληνικά)", "el"),
    "HK:zh-Hant": ("香港 (中文)", "zh-HK"),
    "HU:hu": ("Magyarország (Magyar)", "hu"),
    "ID:id": ("Indonesia (Bahasa Indonesia)", "id"),
    "IE:en": ("Ireland (English)", "en-IE"),
    "IL:he": ("ישראל (עברית)", "he"),
    "IN:en": ("India (English)", "en-IN"),
    "IN:hi": ("भारत (हिन्दी)", "hi"),
    "IT:it": ("Italia (Italiano)", "it"),
    "JP:ja": ("日本 (日本語)", "ja"),
    "KR:ko": ("대한민국 (한국어)", "ko"),
    "MX:es-419": ("México (Español)", "es-419"),
    "NL:nl": ("Nederland (Nederlands)", "nl"),
    "NO:no": ("Norge (Norsk)", "no"),
    "NZ:en": ("New Zealand (English)", "en-NZ"),
    "PE:es-419": ("Perú (Español)", "es-419"),
    "PH:en": ("Philippines (English)", "en-PH"),
    "PL:pl": ("Polska (Polski)", "pl"),
    "PT:pt-150": ("Portugal (Português)", "pt-PT"),
    "RO:ro": ("România (Română)", "ro"),
    "SE:sv": ("Sverige (Svenska)", "sv"),
    "SG:en": ("Singapore (English)", "en-SG"),
    "TR:tr": ("Türkiye (Türkçe)", "tr"),
    "TW:zh-Hant": ("台灣 (中文)", "zh-TW"),
    "UA:uk": ("Україна (Українська)", "uk"),
    "US:en": ("United States (English)", "en-US"),
    "US:es-419": ("Estados Unidos (Español)", "es-419"),
    "ZA:en": ("South Africa (English)", "en-ZA"),
}
DEFAULT_EDITION = "US:en"

WHEN = ("any", "1d", "7d")  # any time, past day, past week


def build_url(query: str, edition: str, when: str = "any") -> str:
    """The RSS address for a search. Unknown editions fall back to the default."""
    if edition not in EDITIONS:
        edition = DEFAULT_EDITION
    q = " ".join(query.split())
    if when in WHEN and when != "any":
        q = f"{q} when:{when}"
    gl = edition.split(":", 1)[0]
    params = {"q": q, "hl": EDITIONS[edition][1], "gl": gl, "ceid": edition}
    return f"{SEARCH_URL}?{urlencode(params)}"


def default_edition(language: str | None, country: str | None) -> str:
    """The edition closest to Home Assistant's language and country
    (e.g. "pt-BR" and "BR" -> Brasil)."""
    lang = (language or "").lower().replace("_", "-")
    base = lang.split("-", 1)[0]
    country = (country or "").upper()

    def lang_of(ed: str) -> str:
        return ed.split(":", 1)[1].split("-", 1)[0].lower()

    same_country = [ed for ed in EDITIONS if ed.split(":", 1)[0] == country]
    for ed in same_country:  # country and language
        if lang_of(ed) == base:
            return ed
    if same_country:  # the country's edition, other language
        return same_country[0]
    # No country: the language's own country if HA has one ("pt-BR"),
    # else its first edition.
    region = lang.split("-", 1)[1].upper() if "-" in lang else ""
    for ed in EDITIONS:
        if lang_of(ed) == base and ed.split(":", 1)[0] == region:
            return ed
    for ed in sorted(EDITIONS, key=lambda e: e != DEFAULT_EDITION):
        if lang_of(ed) == base:
            return ed
    return DEFAULT_EDITION
