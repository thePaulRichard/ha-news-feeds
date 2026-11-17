"""Fetch an RSS or Atom feed and keep its newest headlines.

Standard library only. Feed text is untrusted: summaries are reduced to
plain text here, links must be http(s) and pictures https. ElementTree
never loads external entities, and expat limits entity expansion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import re
import unicodedata
import xml.etree.ElementTree as ET

MEDIA_NS = "http://search.yahoo.com/mrss/"
MAX_BYTES = 5 * 1024 * 1024  # bigger than any news feed we know (g1: ~500 KB)
SUMMARY_CHARS = 300


def _fold(text: str) -> str:
    """Lower case, without accents: "São Paulo" matches "sao paulo"."""
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def keywords(value: str) -> re.Pattern | None:
    """Comma-separated words or phrases, as one pattern matching any of
    them as whole words ("ai" doesn't match "rain"). None when empty."""
    words = {" ".join(_fold(w).split()) for w in (value or "").split(",")}
    words.discard("")
    if not words:
        return None
    alts = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alts})(?!\w)")


class FeedError(Exception):
    """The feed couldn't be read."""


class _Text(HTMLParser):
    """HTML to text, plus the first picture (for feeds that only have
    one inside the summary)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.img = ""
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "img" and not self.img:
            self.img = dict(attrs).get("src") or ""

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _html_text(html: str) -> tuple[str, str]:
    p = _Text()
    try:
        p.feed(html)
        p.close()
    except Exception:  # noqa: BLE001 - broken HTML: keep what we have
        pass
    return " ".join("".join(p.parts).split()), p.img


def _ns(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(el: ET.Element | None) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def _date(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        d = parsedate_to_datetime(value)  # RSS: RFC 822
    except (TypeError, ValueError, IndexError):
        try:
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))  # Atom
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _https(url: str) -> str:
    return url if url.lower().startswith("https://") else ""


def _image(item: ET.Element) -> str:
    for el in item.iter():
        if el is item:
            continue
        name, ns = _local(el.tag), _ns(el.tag)
        url = el.get("url") or ""
        if ns == MEDIA_NS and name == "thumbnail":
            if _https(url):
                return url
        elif (ns == MEDIA_NS and name == "content") or name == "enclosure":
            kind = el.get("medium") or el.get("type") or ("image" if ns == MEDIA_NS else "")
            if "image" in kind and _https(url):
                return url
    return ""


def _item(item: ET.Element) -> dict | None:
    kids: dict[str, list[ET.Element]] = {}
    for el in item:
        if _ns(el.tag) != MEDIA_NS:
            kids.setdefault(_local(el.tag), []).append(el)

    def first(*names: str) -> ET.Element | None:
        for n in names:
            if n in kids:
                return kids[n][0]
        return None

    title, _ = _html_text(_text(first("title")))
    # Aggregators (Google News) name the original site in <source> and
    # repeat it at the end of the title: "Headline - The Verge".
    source = _text(first("source"))
    if source and title.endswith(f" - {source}"):
        title = title[: -len(source) - 3].rstrip()
    if not title:
        return None

    link = ""
    for el in kids.get("link", []):
        href = el.get("href")  # Atom
        if href is not None:
            if el.get("rel", "alternate") == "alternate":
                link = href.strip()
                break
        elif _text(el):  # RSS
            link = _text(el)
            break
    if not link:
        guid = first("guid")
        if guid is not None and guid.get("isPermaLink", "true") == "true":
            link = _text(guid)
    if not link.lower().startswith(("http://", "https://")):
        link = ""

    published = None
    for n in ("pubDate", "published", "updated", "date"):
        if (published := _date(_text(first(n)))) is not None:
            break

    body = first("description", "summary", "content", "encoded")
    summary, img = _html_text("".join(body.itertext()) if body is not None else "")
    for n in ("content", "encoded"):  # a picture in the full article
        if img:
            break
        for el in kids.get(n, []):
            if el is not body and (img := _html_text("".join(el.itertext()))[1]):
                break
    if summary in (title, f"{title} {source}"):  # Google News: title + site
        summary = ""
    if len(summary) > SUMMARY_CHARS:
        summary = summary[: SUMMARY_CHARS - 1].rstrip() + "…"

    return {
        "title": title[:250],
        "link": link,
        "published": published.isoformat() if published else None,
        "summary": summary,
        "image": _image(item) or _https(img),
        "_ts": published.timestamp() if published else None,
    }


def parse(
    data: bytes,
    limit: int,
    include: re.Pattern | None = None,
    exclude: re.Pattern | None = None,
) -> tuple[str, list[dict]]:
    """The feed's own title and its newest `limit` items, keeping only
    those whose title or summary matches `include` (when given) and not
    `exclude`, and skipping repeated titles. Raises FeedError when the
    data isn't a feed; a feed with no (matching) items gives []."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as err:
        raise FeedError(f"not a feed: {err}") from err
    title = ""
    for el in root.iter():
        if _local(el.tag) in ("channel", "feed"):
            t = next((c for c in el if _local(c.tag) == "title"), None)
            title = _text(t)
            break
    else:
        raise FeedError("not an RSS or Atom feed")
    # A real feed with no items is just empty for now (a search with no
    # news today), not an error.
    items = [i for el in root.iter() if _local(el.tag) in ("item", "entry") if (i := _item(el))]
    # Newest first when every item has a date; otherwise the feed's order.
    if all(i["_ts"] is not None for i in items):
        items.sort(key=lambda i: i["_ts"], reverse=True)
    kept = []
    seen: set[str] = set()
    for i in items:
        del i["_ts"]
        # The same story twice (Google News lists it once per site).
        key = " ".join(_fold(i["title"]).split())
        if key in seen:
            continue
        seen.add(key)
        text = _fold(f"{i['title']} {i['summary']}")
        if include and not include.search(text):
            continue
        if exclude and exclude.search(text):
            continue
        kept.append(i)
        if len(kept) == limit:
            break
    return title, kept
