"""Polls the Plastic Slinger service for active prints and glance state."""

from __future__ import annotations

import copy
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CannotConnect, InvalidAuth, PlasticSlingerApi
from .const import DOMAIN, STALE_DATA_GRACE, scan_interval

_LOGGER = logging.getLogger(__name__)


def farm_device_identifier(entry: ConfigEntry) -> tuple[str, str]:
    """Device registry identifier for this Plastic Slinger config entry."""
    return (DOMAIN, entry.entry_id)


class PlasticSlingerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches the active-prints glance payload in one request."""

    config_entry: PlasticSlingerConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PlasticSlingerConfigEntry, api: PlasticSlingerApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=scan_interval(entry.options),
            always_update=False,
        )
        self.api = api
        self._last_success = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            payload = await self.api.async_get_glance()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed("The Plastic Slinger API key was rejected") from err
        except CannotConnect as err:
            if self.data is not None and self._last_success and dt_util.utcnow() - self._last_success < STALE_DATA_GRACE:
                _LOGGER.warning("Plastic Slinger is unreachable (%s); keeping the last data for now", err)
                return self.data
            raise UpdateFailed(f"Can't reach Plastic Slinger: {err}") from err

        self._last_success = dt_util.utcnow()
        return payload

    def has_printer(self, printer_id: int) -> bool:
        """Whether this entry's glance list currently includes that printer."""
        return any(
            int(p.get("id", -1)) == int(printer_id)
            for p in (self.data or {}).get("printers") or []
        )

    @callback
    def async_remove_dismissed_printer(self, printer_id: int) -> None:
        """Remove a dismissed printer from the coordinator data immediately without waiting for the next poll."""
        if not self.data:
            return
        printers = self.data.get("printers") or []
        remaining = [p for p in printers if int(p.get("id", -1)) != int(printer_id)]
        if len(remaining) == len(printers):
            return
        updated = copy.deepcopy(self.data)
        updated["printers"] = remaining
        updated["active_count"] = len(remaining)
        updated["printing_count"] = sum(1 for p in remaining if p.get("status") == "printing")
        updated["paused_count"] = sum(1 for p in remaining if p.get("status") == "paused")
        updated["complete_count"] = sum(1 for p in remaining if p.get("status") == "complete")
        updated["failed_count"] = sum(1 for p in remaining if p.get("status") == "failed")
        self.async_set_updated_data(updated)


PlasticSlingerConfigEntry = ConfigEntry[PlasticSlingerCoordinator]
