"""Plastic Slinger: active 3D prints and camera snapshots from the self-hosted Plastic Slinger service.

Home Assistant talks only to that service on the LAN, never directly to printers.
"""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import PlasticSlingerApi
from .const import CONF_VERIFY_SSL, DOMAIN, scan_interval
from .coordinator import PlasticSlingerConfigEntry, PlasticSlingerCoordinator
from .http import PlasticSlingerNotificationImageView, PlasticSlingerSnapshotView
from .services import async_setup_services

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration actions and the authenticated snapshot and notification image proxy views."""
    async_setup_services(hass)
    hass.http.register_view(PlasticSlingerSnapshotView())
    hass.http.register_view(PlasticSlingerNotificationImageView())
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PlasticSlingerConfigEntry) -> bool:
    """Set up from a config entry."""
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    api = PlasticSlingerApi(session, entry.data[CONF_URL], entry.data[CONF_API_KEY])

    coordinator = PlasticSlingerCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PlasticSlingerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: PlasticSlingerConfigEntry) -> None:
    """Apply a new polling interval in place (no reload, so entities don't flicker)."""
    entry.runtime_data.update_interval = scan_interval(entry.options)
