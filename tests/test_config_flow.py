"""Config flow, options flow, coordinator and sensor in a real Home Assistant."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_news.const import DOMAIN

URL = "https://feed.example/rss"


def rss(*titles: str) -> bytes:
    items = "".join(
        f"<item><title>{t}</title><link>https://e.example/{n}</link>"
        f"<pubDate>Mon, 16 Nov 2026 {10 - n:02d}:00:00 GMT</pubDate></item>"
        for n, t in enumerate(titles)
    )
    return f'<rss version="2.0"><channel><title>Feed</title>{items}</channel></rss>'.encode()


FEED = rss("Dublin bus strike", "Football in Cork", "Rain in Dublin", "Celebrity gossip")


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    yield


@pytest.fixture
def feed(aioclient_mock):
    aioclient_mock.get(URL, content=FEED)
    return aioclient_mock


@pytest.fixture(autouse=True)
def no_frontend(hass):
    # The cards need frontend/http; not what these tests are about.
    hass.config.components.update({"frontend", "http"})
    with patch("custom_components.ha_news.async_setup", return_value=True):
        yield


async def start(hass, kind="feed"):
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert r["type"] is FlowResultType.MENU
    assert r["menu_options"] == ["feed", "google"]
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": kind})
    assert r["type"] is FlowResultType.FORM
    assert r["step_id"] == kind
    return r


def state(hass):
    s = hass.states.get("sensor.news")
    return s.state, [i["title"] for i in s.attributes["items"]]


async def test_add_with_filter(hass: HomeAssistant, feed) -> None:
    r = await start(hass)
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {"name": "News", "url": URL, "items": 5, "include": " Dublin,, cork ", "exclude": "football"},
    )
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["options"] == {"prefix": "", "items": 5, "include": "Dublin, cork", "exclude": "football"}
    await hass.async_block_till_done()
    assert state(hass) == ("Dublin bus strike", ["Dublin bus strike", "Rain in Dublin"])


async def test_add_without_optional_fields(hass: HomeAssistant, feed) -> None:
    """The frontend leaves empty optional fields out of the reply."""
    r = await start(hass)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"url": URL, "items": 2})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["title"] == "Feed"
    assert r["options"] == {"prefix": "", "items": 2, "include": "", "exclude": ""}
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 1


async def entry(hass, **options) -> MockConfigEntry:
    e = MockConfigEntry(
        domain=DOMAIN, title="News", data={"url": URL}, unique_id=URL,
        options={"prefix": "", "items": 5, **options},
    )
    e.add_to_hass(hass)
    assert await hass.config_entries.async_setup(e.entry_id)
    await hass.async_block_till_done()
    return e


async def test_old_entry_without_filter_keys(hass: HomeAssistant, feed) -> None:
    """Entries made by 0.1.x have no include/exclude: every headline."""
    await entry(hass)
    assert len(state(hass)[1]) == 4


async def test_empty_feed_loads(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(URL, content=rss())
    e = await entry(hass)
    assert e.state is config_entries.ConfigEntryState.LOADED
    assert state(hass) == ("unknown", [])


async def test_html_page_refused(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(URL, content=b"<html><body>no feed</body></html>")
    r = await start(hass)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"url": URL, "items": 5})
    assert r["errors"] == {"base": "cannot_read"}


async def test_nothing_matches(hass: HomeAssistant, feed) -> None:
    e = await entry(hass, include="zzz")
    assert e.state is config_entries.ConfigEntryState.LOADED
    assert state(hass) == ("unknown", [])


async def test_options_shows_and_clears_filter(hass: HomeAssistant, feed) -> None:
    e = await entry(hass, include="dublin", exclude="rain")
    assert state(hass)[1] == ["Dublin bus strike"]

    r = await hass.config_entries.options.async_init(e.entry_id)
    schema = {str(k): k for k in r["data_schema"].schema}
    assert schema["include"].description == {"suggested_value": "dublin"}
    assert schema["exclude"].description == {"suggested_value": "rain"}

    # Emptying a field: the frontend sends nothing for it. It must clear,
    # not come back with the old value.
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"url": URL, "items": 5})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert e.options == {"url": URL, "prefix": "", "items": 5, "include": "", "exclude": ""}
    await hass.async_block_till_done()
    assert len(state(hass)[1]) == 4  # reloaded with no filter


async def test_options_change_filter_reloads(hass: HomeAssistant, feed) -> None:
    e = await entry(hass)
    r = await hass.config_entries.options.async_init(e.entry_id)
    await hass.config_entries.options.async_configure(
        r["flow_id"], {"url": URL, "items": 1, "exclude": "dublin"}
    )
    await hass.async_block_till_done()
    assert state(hass) == ("Football in Cork", ["Football in Cork"])


# ---- Google News search ----

GFEED = (
    b'<rss version="2.0"><channel><title>"x" - Google News</title>'
    b"<item><title>RAM prices rise - Site A</title><link>https://news.google.com/a</link>"
    b"<pubDate>Mon, 16 Nov 2026 10:00:00 GMT</pubDate><source url='https://a'>Site A</source></item>"
    b"<item><title>RAM prices rise - Site B</title><link>https://news.google.com/b</link>"
    b"<pubDate>Mon, 16 Nov 2026 09:00:00 GMT</pubDate><source url='https://b'>Site B</source></item>"
    b"<item><title>RAM and futebol - Site C</title><link>https://news.google.com/c</link>"
    b"<pubDate>Mon, 16 Nov 2026 08:00:00 GMT</pubDate><source url='https://c'>Site C</source></item>"
    b"</channel></rss>"
)
GURL = "https://news.google.com/rss/search"


@pytest.fixture
def google(aioclient_mock):
    aioclient_mock.get(GURL, content=GFEED)  # any query string
    return aioclient_mock


async def test_google_add(hass: HomeAssistant, google) -> None:
    hass.config.language = "pt-BR"
    hass.config.country = "BR"
    r = await start(hass, "google")
    schema = {str(k): k for k in r["data_schema"].schema}
    assert schema["edition"].default() == "BR:pt-419"
    assert schema["when"].default() == "any"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {"query": "  ram   price ", "edition": "BR:pt-419", "when": "7d", "items": 5, "exclude": "futebol"},
    )
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["title"] == "ram price"
    assert r["data"] == {"source": "google"}
    assert r["options"] == {
        "query": "ram price", "edition": "BR:pt-419", "when": "7d",
        "prefix": "", "items": 5, "exclude": "",
    } | {"exclude": "futebol"}
    await hass.async_block_till_done()
    url = google.mock_calls[-1][1]
    assert str(url).startswith(GURL + "?")
    assert dict(url.query) == {"q": "ram price when:7d", "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"}
    s = hass.states.get("sensor.ram_price")
    assert s.state == "RAM prices rise"
    assert [i["title"] for i in s.attributes["items"]] == ["RAM prices rise"]  # deduped, filtered


async def test_google_name_and_duplicate(hass: HomeAssistant, google) -> None:
    r = await start(hass, "google")
    data = {"query": "x", "edition": "IE:en", "when": "any", "items": 5, "name": "My news"}
    r = await hass.config_entries.flow.async_configure(r["flow_id"], data)
    assert r["title"] == "My news"
    r = await start(hass, "google")
    r = await hass.config_entries.flow.async_configure(r["flow_id"], data)
    assert r["type"] is FlowResultType.ABORT
    assert r["reason"] == "already_configured"


async def test_google_empty_query(hass: HomeAssistant, google) -> None:
    r = await start(hass, "google")
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"query": "   ", "edition": "IE:en", "when": "any", "items": 5}
    )
    assert r["type"] is FlowResultType.FORM
    assert r["errors"] == {"query": "empty_query"}
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"query": "a" * 301, "edition": "IE:en", "when": "any", "items": 5}
    )
    assert r["errors"] == {"query": "long_query"}


async def test_google_unreachable(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(GURL, status=503)
    r = await start(hass, "google")
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"query": "x", "edition": "IE:en", "when": "any", "items": 5}
    )
    assert r["errors"] == {"base": "cannot_reach_google"}


async def test_google_no_results_ok(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(GURL, content=b'<rss version="2.0"><channel><title>G</title></channel></rss>')
    r = await start(hass, "google")
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"query": "zzqq", "edition": "IE:en", "when": "1d", "items": 5}
    )
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("sensor.zzqq").state == "unknown"


async def test_google_options(hass: HomeAssistant, google) -> None:
    e = MockConfigEntry(
        domain=DOMAIN, title="gpu", data={"source": "google"},
        options={"query": "gpu", "edition": "BR:pt-419", "when": "any", "prefix": "", "items": 5, "exclude": ""},
    )
    e.add_to_hass(hass)
    assert await hass.config_entries.async_setup(e.entry_id)
    await hass.async_block_till_done()

    r = await hass.config_entries.options.async_init(e.entry_id)
    assert r["step_id"] == "google"
    schema = {str(k): k for k in r["data_schema"].schema}
    assert "url" not in schema and "name" not in schema
    assert schema["query"].default() == "gpu"
    assert schema["edition"].default() == "BR:pt-419"

    calls = google.call_count
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"query": "gpu stock", "edition": "PT:pt-150", "when": "1d", "items": 3}
    )
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert e.options["query"] == "gpu stock" and e.options["edition"] == "PT:pt-150"
    assert e.options["exclude"] == ""
    await hass.async_block_till_done()
    url = google.mock_calls[-1][1]
    assert dict(url.query) == {"q": "gpu stock when:1d", "hl": "pt-PT", "gl": "PT", "ceid": "PT:pt-150"}
    assert google.call_count > calls

    # An empty search is refused in Configure too.
    r = await hass.config_entries.options.async_init(e.entry_id)
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"query": "", "edition": "PT:pt-150", "when": "1d", "items": 3}
    )
    assert r["errors"] == {"query": "empty_query"}


async def test_feed_options_step(hass: HomeAssistant, feed) -> None:
    e = await entry(hass)
    r = await hass.config_entries.options.async_init(e.entry_id)
    assert r["step_id"] == "feed"
    schema = {str(k): k for k in r["data_schema"].schema}
    assert schema["url"].default() == URL
    assert "query" not in schema


async def test_translations_cover_forms(hass: HomeAssistant) -> None:
    import json
    from pathlib import Path

    import custom_components.ha_news as pkg

    s = json.loads((Path(pkg.__file__).parent / "strings.json").read_text())
    assert set(s["config"]["step"]["user"]["menu_options"]) == {"feed", "google"}
    assert set(s["selector"]["when"]["options"]) == {"any", "1d", "7d"}
    from custom_components.ha_news import config_flow as cf

    defaults = {"edition": "US:en"}
    for where, step, schema in (
        ("config", "feed", cf._feed_schema({}, True)),
        ("config", "google", cf._google_schema(defaults, True)),
        ("options", "feed", cf._feed_schema({}, False)),
        ("options", "google", cf._google_schema(defaults, False)),
    ):
        assert {str(k) for k in schema.schema} == set(s[where]["step"][step]["data"]), (where, step)
    errors = {"invalid_url", "cannot_read", "empty_query", "long_query", "cannot_reach_google"}
    assert set(s["config"]["error"]) == errors == set(s["options"]["error"])
