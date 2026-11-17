"""google.py: building addresses and picking the edition."""

import unittest
from urllib.parse import parse_qs, urlsplit

from custom_components.ha_news.google import DEFAULT_EDITION, EDITIONS, build_url, default_edition


def q(url):
    p = urlsplit(url)
    assert (p.scheme, p.netloc, p.path) == ("https", "news.google.com", "/rss/search"), url
    return {k: v[0] for k, v in parse_qs(p.query).items()}


class Build(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(
            q(build_url("ram price", "BR:pt-419")),
            {"q": "ram price", "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"},
        )

    def test_when(self):
        self.assertEqual(q(build_url("x", "IE:en", "7d"))["q"], "x when:7d")
        self.assertEqual(q(build_url("x", "IE:en", "1d"))["q"], "x when:1d")
        self.assertEqual(q(build_url("x", "IE:en", "any"))["q"], "x")
        self.assertEqual(q(build_url("x", "IE:en", "bogus"))["q"], "x")

    def test_operators_and_unicode_encoded(self):
        url = build_url('"São Paulo" OR rio -futebol & site:g1.globo.com #1 +x', "BR:pt-419")
        self.assertNotIn(" ", url)
        self.assertNotIn('"', url)
        self.assertEqual(q(url)["q"], '"São Paulo" OR rio -futebol & site:g1.globo.com #1 +x')
        self.assertEqual(q(url)["hl"], "pt-BR")  # "&" in the search didn't leak

    def test_spaces_tidied(self):
        self.assertEqual(q(build_url("  a \n  b ", "US:en"))["q"], "a b")

    def test_unknown_edition(self):
        self.assertEqual(q(build_url("x", "XX:zz"))["ceid"], DEFAULT_EDITION)
        self.assertEqual(q(build_url("x", ""))["ceid"], DEFAULT_EDITION)

    def test_editions_consistent(self):
        for ed, (label, hl) in EDITIONS.items():
            gl, lang = ed.split(":")
            self.assertEqual(len(gl), 2, ed)
            self.assertEqual(hl.split("-")[0], lang.split("-")[0], ed)
            self.assertTrue(label, ed)
        labels = [l for l, _ in EDITIONS.values()]
        self.assertEqual(len(labels), len(set(labels)))


class Default(unittest.TestCase):
    def test_cases(self):
        cases = {
            ("pt-BR", "BR"): "BR:pt-419",
            ("pt", "PT"): "PT:pt-150",
            ("pt-BR", None): "BR:pt-419",
            ("pt", None): "BR:pt-419",  # first Portuguese edition
            ("en", "IE"): "IE:en",
            ("en-GB", None): "GB:en",
            ("en", None): "US:en",
            ("fr", "CA"): "CA:fr",
            ("en", "CA"): "CA:en",
            ("de", "BE"): "BE:fr",  # country wins: Belgium's first edition
            ("es", "US"): "US:es-419",
            ("zh-Hant", "TW"): "TW:zh-Hant",
            ("ga", "IE"): "IE:en",
            ("xx", "ZZ"): "US:en",
            (None, None): "US:en",
            ("", ""): "US:en",
            ("en_GB", None): "GB:en",
        }
        for (lang, country), want in cases.items():
            self.assertEqual(default_edition(lang, country), want, (lang, country))
            self.assertIn(default_edition(lang, country), EDITIONS)
