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
    """Add the Active prints sensor for this Plastic Slinger entry."""
    async_add_entities([PlasticSlingerActivePrintsSensor(entry.runtime_data)])


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
