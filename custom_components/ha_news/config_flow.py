"""Add a feed (one entry per feed), and change it with Configure.

Two kinds of feed: an RSS/Atom address, or a Google News search (stored
as the search, edition and time range; the address is built from them).
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_EDITION,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    CONF_ITEMS,
    CONF_PREFIX,
    CONF_QUERY,
    CONF_SOURCE,
    CONF_WHEN,
    DEFAULT_ITEMS,
    DOMAIN,
    MAX_ITEMS,
    MAX_QUERY,
    SOURCE_GOOGLE,
)
from .coordinator import async_fetch, entry_url, redact
from .feed import FeedError
from .google import EDITIONS, WHEN, build_url, default_edition

_LOGGER = logging.getLogger(__name__)

URL = TextSelector(TextSelectorConfig(type=TextSelectorType.URL))
ITEMS = NumberSelector(NumberSelectorConfig(min=1, max=MAX_ITEMS, step=1, mode=NumberSelectorMode.BOX))
EDITION = SelectSelector(
    SelectSelectorConfig(
        options=[
            SelectOptionDict(value=ed, label=label)
            for ed, (label, _) in sorted(EDITIONS.items(), key=lambda e: e[1][0].casefold())
        ],
        mode=SelectSelectorMode.DROPDOWN,
    )
)
WHEN_SELECT = SelectSelector(
    SelectSelectorConfig(options=list(WHEN), translation_key=CONF_WHEN, mode=SelectSelectorMode.LIST)
)


def _optional(defaults: dict, key: str) -> vol.Optional:
    # Optional text fields use suggested_value, not default: with a
    # default, emptying the field would quietly bring the old value back.
    return vol.Optional(key, description={"suggested_value": defaults.get(key, "")})


def _feed_schema(defaults: dict, with_name: bool) -> vol.Schema:
    fields: dict = {}
    if with_name:
        fields[_optional(defaults, CONF_NAME)] = TextSelector()
    fields[vol.Required(CONF_URL, default=defaults.get(CONF_URL, ""))] = URL
    fields[_optional(defaults, CONF_PREFIX)] = TextSelector()
    fields[vol.Required(CONF_ITEMS, default=defaults.get(CONF_ITEMS, DEFAULT_ITEMS))] = ITEMS
    fields[_optional(defaults, CONF_INCLUDE)] = TextSelector()
    fields[_optional(defaults, CONF_EXCLUDE)] = TextSelector()
    return vol.Schema(fields)


def _google_schema(defaults: dict, with_name: bool) -> vol.Schema:
    fields: dict = {
        vol.Required(CONF_QUERY, default=defaults.get(CONF_QUERY, "")): TextSelector(),
        vol.Required(CONF_EDITION, default=defaults[CONF_EDITION]): EDITION,
        vol.Required(CONF_WHEN, default=defaults.get(CONF_WHEN, "any")): WHEN_SELECT,
    }
    if with_name:
        fields[_optional(defaults, CONF_NAME)] = TextSelector()
    fields[_optional(defaults, CONF_PREFIX)] = TextSelector()
    fields[vol.Required(CONF_ITEMS, default=defaults.get(CONF_ITEMS, DEFAULT_ITEMS))] = ITEMS
    fields[_optional(defaults, CONF_EXCLUDE)] = TextSelector()
    return vol.Schema(fields)


def _words(value: str | None) -> str:
    """Tidy a comma-separated list for storage: "a,  b ,," -> "a, b"."""
    return ", ".join(w for w in (" ".join(x.split()) for x in (value or "").split(",")) if w)


def _feed_options(user_input: dict) -> dict:
    return {
        CONF_PREFIX: user_input.get(CONF_PREFIX, "").strip(),
        CONF_ITEMS: int(user_input[CONF_ITEMS]),
        CONF_INCLUDE: _words(user_input.get(CONF_INCLUDE)),
        CONF_EXCLUDE: _words(user_input.get(CONF_EXCLUDE)),
    }


def _google_options(user_input: dict) -> dict:
    """The search as stored; fields the form left out get safe values."""
    edition = user_input.get(CONF_EDITION)
    when = user_input.get(CONF_WHEN)
    return {
        CONF_QUERY: " ".join(user_input.get(CONF_QUERY, "").split()),
        CONF_EDITION: edition if edition in EDITIONS else default_edition(None, None),
        CONF_WHEN: when if when in WHEN else "any",
        CONF_PREFIX: user_input.get(CONF_PREFIX, "").strip(),
        CONF_ITEMS: int(user_input[CONF_ITEMS]),
        CONF_EXCLUDE: _words(user_input.get(CONF_EXCLUDE)),
    }


async def _check(hass: HomeAssistant, url: str) -> tuple[str, dict]:
    """Fetch the feed once. Returns (feed title, errors)."""
    if not url.lower().startswith(("http://", "https://")):
        return "", {CONF_URL: "invalid_url"}
    try:
        title, _ = await async_fetch(hass, url, 1)
    except FeedError as err:
        _LOGGER.warning("Can't read %s: %s", redact(url), err)
        return "", {"base": "cannot_read"}
    return title, {}


async def _check_google(hass: HomeAssistant, options: dict) -> dict:
    """Errors for a search. No results is fine: news may come later."""
    if not options[CONF_QUERY]:
        return {CONF_QUERY: "empty_query"}
    if len(options[CONF_QUERY]) > MAX_QUERY:
        return {CONF_QUERY: "long_query"}
    _, errors = await _check(hass, build_url(options[CONF_QUERY], options[CONF_EDITION], options[CONF_WHEN]))
    return {"base": "cannot_reach_google"} if errors else {}


class NewsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["feed", SOURCE_GOOGLE])

    async def async_step_feed(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip()
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            title, errors = await _check(self.hass, url)
            if not errors:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "").strip() or title or url,
                    data={CONF_URL: url},
                    options=_feed_options(user_input),
                )
        return self.async_show_form(
            step_id="feed", data_schema=_feed_schema(user_input or {}, True), errors=errors
        )

    async def async_step_google(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict = {}
        if user_input is not None:
            options = _google_options(user_input)
            url = build_url(options[CONF_QUERY], options[CONF_EDITION], options[CONF_WHEN])
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            errors = await _check_google(self.hass, options)
            if not errors:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "").strip() or options[CONF_QUERY],
                    data={CONF_SOURCE: SOURCE_GOOGLE},
                    options=options,
                )
        defaults = user_input or {
            CONF_EDITION: default_edition(self.hass.config.language, self.hass.config.country)
        }
        return self.async_show_form(
            step_id=SOURCE_GOOGLE, data_schema=_google_schema(defaults, True), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NewsOptionsFlow()


class NewsOptionsFlow(OptionsFlow):
    """Change a feed: its address or search, picture prefix, how many
    headlines and the keyword filter. (Rename it with the entry's own
    Rename.)"""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self.config_entry.data.get(CONF_SOURCE) == SOURCE_GOOGLE:
            return await self.async_step_google(user_input)
        return await self.async_step_feed(user_input)

    async def async_step_feed(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        errors: dict = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip()
            if url != entry_url(entry):
                _, errors = await _check(self.hass, url)
            if not errors:
                return self.async_create_entry(data={CONF_URL: url, **_feed_options(user_input)})
        defaults = user_input or {
            CONF_URL: entry_url(entry),
            CONF_PREFIX: entry.options.get(CONF_PREFIX, ""),
            CONF_ITEMS: entry.options.get(CONF_ITEMS, DEFAULT_ITEMS),
            CONF_INCLUDE: entry.options.get(CONF_INCLUDE, ""),
            CONF_EXCLUDE: entry.options.get(CONF_EXCLUDE, ""),
        }
        return self.async_show_form(
            step_id="feed", data_schema=_feed_schema(defaults, False), errors=errors
        )

    async def async_step_google(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        errors: dict = {}
        if user_input is not None:
            options = _google_options(user_input)
            url = build_url(options[CONF_QUERY], options[CONF_EDITION], options[CONF_WHEN])
            if url != entry_url(entry) or not options[CONF_QUERY]:
                errors = await _check_google(self.hass, options)
            if not errors:
                return self.async_create_entry(data=options)
        defaults = user_input or {
            **entry.options,
            CONF_EDITION: entry.options.get(CONF_EDITION) or default_edition(None, None),
        }
        return self.async_show_form(
            step_id=SOURCE_GOOGLE, data_schema=_google_schema(defaults, False), errors=errors
        )
