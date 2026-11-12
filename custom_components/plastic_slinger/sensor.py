"""Active prints sensor for the Plastic Slinger glance card."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PlasticSlingerConfigEntry, PlasticSlingerCoordinator, farm_device_identifier

_PAYLOAD_ATTRIBUTES = (
    "sort_mode",
    "status_colors",
    "active_count",
    "printing_count",
    "paused_count",
    "complete_count",
    "failed_count",
    "printers",
    "generated_at",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlasticSlingerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the Active prints and Notifications sensors for this Plastic Slinger entry."""
    async_add_entities(
        [
            PlasticSlingerActivePrintsSensor(entry.runtime_data),
            PlasticSlingerNotificationsSensor(entry.runtime_data),
        ]
    )


class PlasticSlingerActivePrintsSensor(CoordinatorEntity[PlasticSlingerCoordinator], SensorEntity):
    """Number of active/held printers on the glance view; the tiles and status colors are in the attributes."""

    _attr_has_entity_name = True
    _attr_translation_key = "active_prints"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "printers"
    # Keep the printer tile list and status colors out of the SQLite recorder history.
    _unrecorded_attributes = frozenset({"printers", "status_colors"})

    def __init__(self, coordinator: PlasticSlingerCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_active_prints"
        self._attr_device_info = DeviceInfo(
            identifiers={farm_device_identifier(entry)},
            name="Plastic Slinger",
            manufacturer="Plastic Slinger",
            model="3D Print Farm Manager",
            configuration_url=entry.data.get(CONF_URL),
        )

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data
        if data is None:
            return None
        printers = data.get("printers")
        if isinstance(printers, list):
            return len(printers)
        return int(data.get("active_count", 0))

    @property
    def icon(self) -> str:
        count = self.native_value or 0
        return "mdi:printer-3d-nozzle" if count > 0 else "mdi:printer-3d"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {key: data.get(key) for key in _PAYLOAD_ATTRIBUTES if key in data}


class PlasticSlingerNotificationsSensor(CoordinatorEntity[PlasticSlingerCoordinator], SensorEntity):
    """Number of active alerts in the Plastic Slinger visual notification feed; items are in the attributes."""

    _attr_has_entity_name = True
    _attr_translation_key = "notifications"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "alerts"
    # Keep the notification list and status colors out of the SQLite recorder history.
    _unrecorded_attributes = frozenset({"notifications", "status_colors"})

    def __init__(self, coordinator: PlasticSlingerCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_notifications"
        self._attr_device_info = DeviceInfo(
            identifiers={farm_device_identifier(entry)},
            name="Plastic Slinger",
            manufacturer="Plastic Slinger",
            model="3D Print Farm Manager",
            configuration_url=entry.data.get(CONF_URL),
        )

    def _feed(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return data.get("notifications_feed") or {}

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        feed = self._feed()
        if "active_count" in feed:
            return int(feed.get("active_count", 0))
        items = feed.get("notifications")
        if isinstance(items, list):
            return len([n for n in items if not n.get("is_dismissed")])
        return 0

    @property
    def icon(self) -> str:
        feed = self._feed()
        if int(feed.get("critical_count", 0)) > 0 or int(feed.get("warning_count", 0)) > 0:
            return "mdi:bell-alert"
        if (self.native_value or 0) > 0:
            return "mdi:bell-badge"
        return "mdi:bell-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        feed = self._feed()
        colors = feed.get("colors") or data.get("status_colors") or {}
        notifications = feed.get("notifications")
        if not isinstance(notifications, list):
            notifications = []
        return {
            "active_count": int(feed.get("active_count", len(notifications))),
            "unread_count": int(feed.get("unread_count", len(notifications))),
            "critical_count": int(feed.get("critical_count", 0)),
            "warning_count": int(feed.get("warning_count", 0)),
            "status_colors": colors,
            "notifications": notifications,
        }
