"""News: headlines from RSS and Atom feeds, for the dashboard.

Each feed is one config entry (Settings > Devices & services > Add
integration > News) and one sensor: state = newest headline, attribute
`items` = the newest headlines with link, time, summary and picture.
The integration also loads two cards on every dashboard, no resource to
register: custom:news-ticker-card and custom:news-feed-card.
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CARDS, DOMAIN, PLATFORMS, STATIC_URL
from .coordinator import FeedCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the cards and load them on every page."""
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    www = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(www), False)]
    )
    for name in CARDS:
        # The file's time in the URL, so browsers fetch a changed card.
        version = (await hass.async_add_executor_job((www / name).stat)).st_mtime_ns
        add_extra_js_url(hass, f"{STATIC_URL}/{name}?v={version}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = FeedCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Options or the title changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
