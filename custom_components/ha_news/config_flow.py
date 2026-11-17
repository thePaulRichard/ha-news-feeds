"""Add a feed (one entry per feed), and change it with Configure."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_ITEMS, CONF_PREFIX, DEFAULT_ITEMS, DOMAIN, MAX_ITEMS
from .coordinator import async_fetch
from .feed import FeedError

_LOGGER = logging.getLogger(__name__)

URL = TextSelector(TextSelectorConfig(type=TextSelectorType.URL))
ITEMS = NumberSelector(NumberSelectorConfig(min=1, max=MAX_ITEMS, step=1, mode=NumberSelectorMode.BOX))


def _schema(defaults: dict, with_name: bool) -> vol.Schema:
    fields: dict = {}
    if with_name:
        fields[vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, ""))] = TextSelector()
    fields[vol.Required(CONF_URL, default=defaults.get(CONF_URL, ""))] = URL
    fields[vol.Optional(CONF_PREFIX, default=defaults.get(CONF_PREFIX, ""))] = TextSelector()
    fields[vol.Required(CONF_ITEMS, default=defaults.get(CONF_ITEMS, DEFAULT_ITEMS))] = ITEMS
    return vol.Schema(fields)


async def _check(hass, user_input: dict) -> tuple[str, dict]:
    """Fetch the feed once. Returns (feed title, errors)."""
    url = user_input[CONF_URL].strip()
    if not url.lower().startswith(("http://", "https://")):
        return "", {CONF_URL: "invalid_url"}
    try:
        title, _ = await async_fetch(hass, url, 1)
    except FeedError as err:
        _LOGGER.warning("Can't read %s: %s", url, err)
        return "", {"base": "cannot_read"}
    return title, {}


class NewsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip()
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            title, errors = await _check(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "").strip() or title or url,
                    data={CONF_URL: url},
                    options={
                        CONF_PREFIX: user_input.get(CONF_PREFIX, "").strip(),
                        CONF_ITEMS: int(user_input[CONF_ITEMS]),
                    },
                )
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}, True), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NewsOptionsFlow()


class NewsOptionsFlow(OptionsFlow):
    """The feed's address, picture prefix and how many headlines.
    (Rename the feed with the entry's own Rename.)"""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        errors: dict = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip()
            if url != (entry.options.get(CONF_URL) or entry.data[CONF_URL]):
                _, errors = await _check(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    data={
                        CONF_URL: url,
                        CONF_PREFIX: user_input.get(CONF_PREFIX, "").strip(),
                        CONF_ITEMS: int(user_input[CONF_ITEMS]),
                    }
                )
        defaults = user_input or {
            CONF_URL: entry.options.get(CONF_URL) or entry.data[CONF_URL],
            CONF_PREFIX: entry.options.get(CONF_PREFIX, ""),
            CONF_ITEMS: entry.options.get(CONF_ITEMS, DEFAULT_ITEMS),
        }
        return self.async_show_form(
            step_id="init", data_schema=_schema(defaults, False), errors=errors
        )
