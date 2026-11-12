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

from .api import CannotConnect, InvalidAuth, NotFound, PlasticSlingerApi
from .const import DOMAIN, STALE_DATA_GRACE, scan_interval

_LOGGER = logging.getLogger(__name__)


def farm_device_identifier(entry: ConfigEntry) -> tuple[str, str]:
    """Device registry identifier for this Plastic Slinger config entry."""
    return (DOMAIN, entry.entry_id)


class PlasticSlingerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches the active-prints glance payload and visual notifications feed."""

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

        try:
            notifications_feed = await self.api.async_get_notifications()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed("The Plastic Slinger API key was rejected") from err
        except (NotFound, CannotConnect):
            prev_feed = (self.data or {}).get("notifications_feed")
            notifications_feed = prev_feed or {
                "active_count": 0,
                "unread_count": 0,
                "critical_count": 0,
                "warning_count": 0,
                "colors": payload.get("status_colors") or {},
                "notifications": [],
            }

        payload = dict(payload)
        payload["notifications_feed"] = notifications_feed
        self._last_success = dt_util.utcnow()
        return payload

    def has_printer(self, printer_id: int) -> bool:
        """Whether this entry's glance list currently includes that printer."""
        return any(
            int(p.get("id", -1)) == int(printer_id)
            for p in (self.data or {}).get("printers") or []
        )

    def has_notification(self, notification_id: int) -> bool:
        """Whether this entry's notification feed currently includes that notification."""
        feed = (self.data or {}).get("notifications_feed") or {}
        return any(
            int(n.get("id", -1)) == int(notification_id)
            for n in feed.get("notifications") or []
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

    @callback
    def async_remove_dismissed_notification(self, notification_id: int) -> None:
        """Remove a dismissed notification from the coordinator data immediately without waiting for the next poll."""
        if not self.data:
            return
        feed = (self.data.get("notifications_feed") or {})
        items = feed.get("notifications") or []
        remaining = [n for n in items if int(n.get("id", -1)) != int(notification_id)]
        if len(remaining) == len(items):
            return
        updated = copy.deepcopy(self.data)
        updated_feed = updated.setdefault("notifications_feed", {})
        updated_feed["notifications"] = remaining
        active = [n for n in remaining if not n.get("is_dismissed")]
        updated_feed["active_count"] = len(active)
        updated_feed["unread_count"] = len(active)
        updated_feed["critical_count"] = sum(1 for n in active if str(n.get("severity", "")).lower() == "critical")
        updated_feed["warning_count"] = sum(1 for n in active if str(n.get("severity", "")).lower() == "warning")
        self.async_set_updated_data(updated)

    @callback
    def async_clear_all_notifications(self) -> None:
        """Clear all active notifications from the coordinator data immediately."""
        if not self.data:
            return
        updated = copy.deepcopy(self.data)
        updated_feed = updated.setdefault("notifications_feed", {})
        updated_feed["notifications"] = []
        updated_feed["active_count"] = 0
        updated_feed["unread_count"] = 0
        updated_feed["critical_count"] = 0
        updated_feed["warning_count"] = 0
        self.async_set_updated_data(updated)


PlasticSlingerConfigEntry = ConfigEntry[PlasticSlingerCoordinator]
