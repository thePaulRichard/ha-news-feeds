"""Fetch one feed every 30 minutes."""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlsplit

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_EDITION,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    CONF_ITEMS,
    CONF_QUERY,
    CONF_SOURCE,
    CONF_WHEN,
    DEFAULT_ITEMS,
    DOMAIN,
    SCAN_INTERVAL,
    SOURCE_GOOGLE,
    TIMEOUT,
)
from .feed import MAX_BYTES, FeedError, keywords, parse
from .google import build_url

_LOGGER = logging.getLogger(__name__)


def redact(url: str) -> str:
    """Scheme and host only, for logs: a private feed's address can carry
    a token in its path, query or user part."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return "<feed>"
    return f"{parts.scheme}://{host}{port}" if host else "<feed>"


def entry_url(entry: ConfigEntry) -> str:
    """The address to fetch: built from the search for Google News
    entries, else the one entered (options win over the first one)."""
    o = entry.options
    if entry.data.get(CONF_SOURCE) == SOURCE_GOOGLE:
        return build_url(o.get(CONF_QUERY, ""), o.get(CONF_EDITION, ""), o.get(CONF_WHEN, "any"))
    return o.get(CONF_URL) or entry.data[CONF_URL]


async def async_fetch(
    hass: HomeAssistant,
    url: str,
    limit: int,
    include: re.Pattern | None = None,
    exclude: re.Pattern | None = None,
) -> tuple[str, list[dict]]:
    """Download and parse a feed, keeping the headlines that pass the
    keyword filter. Raises FeedError."""
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(TIMEOUT):
            async with session.get(url, headers={"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"}) as resp:
                if resp.status != 200:
                    raise FeedError(f"HTTP {resp.status}")
                # read(n) returns what has arrived so far, not the whole
                # body: keep reading to the end, stopping past the limit.
                data = bytearray()
                async for chunk in resp.content.iter_chunked(65536):
                    data += chunk
                    if len(data) > MAX_BYTES:
                        raise FeedError("feed bigger than 5 MB")
    except (aiohttp.ClientError, TimeoutError) as err:
        # aiohttp puts the full address in some errors (bad URL, redirects).
        msg = str(err).replace(url, redact(url)) or type(err).__name__
        raise FeedError(f"can't fetch: {msg}") from err
    data = bytes(data)
    return await hass.async_add_executor_job(parse, data, limit, include, exclude)


class FeedCoordinator(DataUpdateCoordinator[list[dict]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=SCAN_INTERVAL,
        )
        self.url = entry_url(entry)
        self.limit = int(entry.options.get(CONF_ITEMS, DEFAULT_ITEMS))
        self.include = keywords(entry.options.get(CONF_INCLUDE, ""))
        self.exclude = keywords(entry.options.get(CONF_EXCLUDE, ""))

    async def _async_update_data(self) -> list[dict]:
        try:
            _, items = await async_fetch(
                self.hass, self.url, self.limit, self.include, self.exclude
            )
        except FeedError as err:
            raise UpdateFailed(str(err)) from err
        return items
