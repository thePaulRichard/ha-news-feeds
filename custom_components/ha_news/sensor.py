"""One sensor per feed: the newest headline, and the rest as `items`."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PREFIX
from .coordinator import FeedCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([NewsSensor(entry.runtime_data, entry)])


class NewsSensor(CoordinatorEntity[FeedCoordinator], SensorEntity):
    _attr_icon = "mdi:newspaper"
    # The headlines change every half hour and only matter now: keep them
    # out of the history database.
    _unrecorded_attributes = frozenset({"items", "link", "prefix"})

    def __init__(self, coordinator: FeedCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title
        self._prefix = entry.options.get(CONF_PREFIX, "")

    @property
    def native_value(self) -> str | None:
        items = self.coordinator.data or []
        return items[0]["title"] if items else None

    @property
    def extra_state_attributes(self) -> dict:
        items = self.coordinator.data or []
        return {
            "prefix": self._prefix,
            "link": items[0]["link"] if items else "",
            "items": items,
        }
