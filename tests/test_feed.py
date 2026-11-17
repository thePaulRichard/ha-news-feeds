"""feed.py: parsing, the keyword filter, repeats and Google News cleanup."""

from pathlib import Path
import time
import unittest

from custom_components.ha_news.feed import FeedError, _fold, keywords, parse

# A Google News search feed, cut down: same structure as the real one.
GN = Path(__file__).parent / "fixtures" / "google_news.xml"


def rss(*items: str) -> bytes:
    return (
        '<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>'
        + "".join(items)
        + "</channel></rss>"
    ).encode()


def item(title, desc="", date=None, source=None):
    d = f"<pubDate>{date}</pubDate>" if date else ""
    s = f'<source url="https://x.example">{source}</source>' if source else ""
    return f"<item><title>{title}</title><link>https://e.example/{abs(hash(title + desc))}</link><description>{desc}</description>{d}{s}</item>"


def titles(data, limit=50, inc="", exc=""):
    return [i["title"] for i in parse(data, limit, keywords(inc), keywords(exc))[1]]


def hit(words, text):
    return bool(keywords(words).search(_fold(text)))


class Keywords(unittest.TestCase):
    def test_empty_is_none(self):
        for v in ("", " ", ",", " , ,, ", None):
            self.assertIsNone(keywords(v), repr(v))

    def test_whole_words(self):
        self.assertTrue(hit("ai", "AI is here"))
        self.assertTrue(hit("ai", "the (AI) boom"))
        self.assertTrue(hit("ai", "Meta's AI."))
        self.assertFalse(hit("ai", "rain"))
        self.assertFalse(hit("ai", "Ireland's air"))
        self.assertFalse(hit("cork", "corkscrew"))

    def test_case_and_accents(self):
        self.assertTrue(hit("sao paulo", "SÃO PAULO"))
        self.assertTrue(hit("São Paulo", "sao paulo"))
        self.assertTrue(hit("eireann", "Dáil Éireann"))
        self.assertTrue(hit("STRASSE", "straße"))  # casefold, not lower
        self.assertTrue(hit("cafe", "Café"))  # combining accent

    def test_phrases_and_spaces(self):
        self.assertTrue(hit("home   assistant", "Home Assistant 2026"))
        self.assertTrue(hit(" home assistant ", "new home assistant release"))
        self.assertFalse(hit("home assistant", "homeassistant"))
        self.assertFalse(hit("home assistant", "home and assistant"))

    def test_regex_chars_are_literal(self):
        self.assertTrue(hit("c++", "Why C++ is back"))
        self.assertFalse(hit("c++", "c and more"))
        self.assertTrue(hit("a.i", "a.i rules"))
        self.assertFalse(hit("a.i", "abi rules"))
        self.assertFalse(hit(".*", "anything"))
        self.assertTrue(hit("(x", "the (x thing"))
        self.assertTrue(hit("u.s.", "U.S. election"))
        keywords("[, ], (, ), \\, ^, $, |, ?, {2}")  # compiles

    def test_overlapping_words(self):
        # Longest first: "home assistant" must not be cut short by "home".
        self.assertTrue(hit("home, home assistant", "home assistant"))
        self.assertTrue(hit("new, new york", "New York rain"))

    def test_numbers_and_unicode_words(self):
        self.assertTrue(hit("2026", "Budget 2026 announced"))
        self.assertFalse(hit("202", "Budget 2026"))
        self.assertTrue(hit("東京", "東京 news"))
        self.assertTrue(hit("ação", "nova acao do governo"))

    def test_many_words_fast(self):
        k = keywords(",".join(f"word{n}" for n in range(2000)))
        text = _fold("x " * 50_000)
        t = time.perf_counter()
        self.assertIsNone(k.search(text))
        self.assertLess(time.perf_counter() - t, 2)


class Filter(unittest.TestCase):
    FEED = rss(
        item("Dublin bus strike", date="Mon, 16 Nov 2026 10:00:00 GMT"),
        item("Football: Cork wins", date="Mon, 16 Nov 2026 09:00:00 GMT"),
        item("Weather", desc="Rain over Dublin tonight", date="Mon, 16 Nov 2026 08:00:00 GMT"),
        item("Celebrity news", date="Mon, 16 Nov 2026 07:00:00 GMT"),
        item("Cork football final in Dublin", date="Mon, 16 Nov 2026 06:00:00 GMT"),
    )

    def test_no_filter(self):
        self.assertEqual(len(titles(self.FEED)), 5)

    def test_include_title_or_summary(self):
        self.assertEqual(
            titles(self.FEED, inc="dublin"),
            ["Dublin bus strike", "Weather", "Cork football final in Dublin"],
        )

    def test_exclude(self):
        self.assertEqual(
            titles(self.FEED, exc="football, celebrity"), ["Dublin bus strike", "Weather"]
        )

    def test_exclude_wins_over_include(self):
        self.assertEqual(titles(self.FEED, inc="dublin", exc="football"), ["Dublin bus strike", "Weather"])

    def test_limit_after_filter(self):
        # Matches are the 1st, 3rd and 5th: limit 2 must give two, not one.
        self.assertEqual(titles(self.FEED, 2, inc="dublin"), ["Dublin bus strike", "Weather"])
        self.assertEqual(titles(self.FEED, 1, inc="celebrity"), ["Celebrity news"])

    def test_nothing_matches_is_not_error(self):
        self.assertEqual(titles(self.FEED, inc="zzz"), [])
        self.assertEqual(titles(self.FEED, exc="dublin, cork, celebrity"), [])

    def test_empty_feed_is_empty(self):
        self.assertEqual(parse(rss(), 5, keywords("x")), ("T", []))
        self.assertEqual(parse(rss(), 5), ("T", []))

    def test_not_a_feed(self):
        for data in (b"<html><body>hi</body></html>", b"<x/>", b"not xml", b""):
            with self.assertRaises(FeedError):
                parse(data, 5)

    def test_atom_empty(self):
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><title>A</title></feed>'
        self.assertEqual(parse(atom, 5), ("A", []))

    def test_html_in_summary_not_matched(self):
        feed = rss(item("A", desc="&lt;a href='https://dublin.example'&gt;link&lt;/a&gt;"))
        self.assertEqual(titles(feed, inc="dublin"), [])

    def test_old_signature(self):
        self.assertEqual(len(parse(self.FEED, 3)[1]), 3)


class Duplicates(unittest.TestCase):
    def test_same_title_once(self):
        f = rss(
            item("Story - Site A", date="Mon, 16 Nov 2026 10:00:00 GMT", source="Site A"),
            item("Story - Site B", date="Mon, 16 Nov 2026 09:00:00 GMT", source="Site B"),
            item("STORY ", date="Mon, 16 Nov 2026 08:00:00 GMT"),
            item("Other", date="Mon, 16 Nov 2026 07:00:00 GMT"),
        )
        got = parse(f, 5)[1]
        self.assertEqual([i["title"] for i in got], ["Story", "Other"])
        self.assertTrue(got[0]["link"])  # the newest copy kept

    def test_limit_counts_unique(self):
        f = rss(*(item("Same") for _ in range(5)), item("Two"))
        self.assertEqual(titles(f, 2), ["Same", "Two"])

    def test_google_sample_no_repeats(self):
        with open(GN, "rb") as fh:
            got = [i["title"].casefold() for i in parse(fh.read(), 100)[1]]
        self.assertEqual(len(got), len(set(got)))


class GoogleNews(unittest.TestCase):
    def test_source_suffix_removed(self):
        f = rss(item("Big news - The Verge", desc="Big news&#160;&#160;The Verge", source="The Verge"))
        i = parse(f, 5)[1][0]
        self.assertEqual(i["title"], "Big news")
        self.assertEqual(i["summary"], "")

    def test_only_matching_suffix(self):
        f = rss(item("Left - right debate", source="The Verge"))
        self.assertEqual(parse(f, 5)[1][0]["title"], "Left - right debate")

    def test_no_source_untouched(self):
        f = rss(item("Big news - The Verge"))
        self.assertEqual(parse(f, 5)[1][0]["title"], "Big news - The Verge")

    def test_title_only_source_kept(self):
        f = rss(item(" - The Verge", source="The Verge"))
        self.assertEqual(len(parse(f, 5)[1]), 1)

    def test_filter_does_not_see_source(self):
        # The site name was removed, so excluding it doesn't drop the item.
        f = rss(item("Big news - Forbes", desc="Big news Forbes", source="Forbes"))
        self.assertEqual(titles(f, exc="forbes"), ["Big news"])

    def test_google_sample(self):
        with open(GN, "rb") as fh:
            data = fh.read()
        items = parse(data, 100)[1]
        self.assertEqual(len(items), 4)  # 5 items, one story twice
        for i in items:
            self.assertFalse(i["title"].endswith((" - Example Times", " - Daily Sample", " - Tech Weekly")), i["title"])
            self.assertTrue(i["link"].startswith("https://news.google.com/"))
            self.assertTrue(i["published"])

    def test_google_sample_filter(self):
        with open(GN, "rb") as fh:
            data = fh.read()
        self.assertEqual(
            titles(data, exc="phone"),
            [
                "RAM prices keep climbing into the new year",
                "Why a DDR5 kit costs twice what it did in spring",
                "Graphics cards and memory: what to buy now",
            ],
        )
        # Whole words: "price" doesn't match "prices".
        self.assertEqual(titles(data, inc="ram price"), ["Phone makers warn of RAM price rises"])

    def test_google_sample_summaries(self):
        with open(GN, "rb") as fh:
            items = parse(fh.read(), 100)[1]
        dup = [i for i in items if i["summary"].startswith(i["title"])]
        self.assertEqual(dup, [], [d["summary"] for d in dup][:3])
