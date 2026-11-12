"""Integration actions for clearing finished prints and controlling active printers."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import InvalidAuth, NotFound, PlasticSlingerError
from .const import (
    ATTR_MODE,
    ATTR_NAMES,
    ATTR_NOTIFICATION_ID,
    ATTR_ON,
    ATTR_PRINTER_ID,
    DOMAIN,
    SERVICE_CANCEL_PRINT,
    SERVICE_DISMISS_ALL_NOTIFICATIONS,
    SERVICE_DISMISS_NOTIFICATION,
    SERVICE_DISMISS_PRINT,
    SERVICE_PAUSE_PRINT,
    SERVICE_RESUME_PRINT,
    SERVICE_SET_AUTO_UNLOAD,
    SERVICE_SET_LIGHT,
    SERVICE_SKIP_PARTS,
)
from .coordinator import PlasticSlingerCoordinator

PRINTER_ID_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PRINTER_ID): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)

NOTIFICATION_ID_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NOTIFICATION_ID): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)

EMPTY_SCHEMA = vol.Schema({})

SET_LIGHT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PRINTER_ID): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(ATTR_ON): cv.boolean,
    }
)

SET_AUTO_UNLOAD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PRINTER_ID): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(ATTR_MODE): vol.In(["off", "once", "always"]),
    }
)

SKIP_PARTS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PRINTER_ID): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(ATTR_NAMES): vol.All(cv.ensure_list, [cv.string], vol.Length(min=1)),
    }
)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions (once, for every config entry)."""

    async def dismiss_print(call: ServiceCall) -> dict:
        printer_id = int(call.data[ATTR_PRINTER_ID])
        coordinator = _coordinator_for(hass, printer_id)
        result = await _run_api_call(printer_id, coordinator.api.async_dismiss_print(printer_id))
        coordinator.async_remove_dismissed_printer(printer_id)
        return {ATTR_PRINTER_ID: printer_id, "dismissed": bool(result.get("dismissed", True))}

    async def pause_print(call: ServiceCall) -> dict:
        printer_id = int(call.data[ATTR_PRINTER_ID])
        coordinator = _coordinator_for(hass, printer_id)
        result = await _run_api_call(printer_id, coordinator.api.async_pause_print(printer_id))
        await coordinator.async_request_refresh()
        return result

    async def resume_print(call: ServiceCall) -> dict:
        printer_id = int(call.data[ATTR_PRINTER_ID])
        coordinator = _coordinator_for(hass, printer_id)
        result = await _run_api_call(printer_id, coordinator.api.async_resume_print(printer_id))
        await coordinator.async_request_refresh()
        return result

    async def cancel_print(call: ServiceCall) -> dict:
        printer_id = int(call.data[ATTR_PRINTER_ID])
        coordinator = _coordinator_for(hass, printer_id)
        result = await _run_api_call(printer_id, coordinator.api.async_cancel_print(printer_id))
        await coordinator.async_request_refresh()
        return result

    async def set_light(call: ServiceCall) -> dict:
        printer_id = int(call.data[ATTR_PRINTER_ID])
        on = call.data.get(ATTR_ON)
        coordinator = _coordinator_for(hass, printer_id)
        result = await _run_api_call(printer_id, coordinator.api.async_set_light(printer_id, on))
        await coordinator.async_request_refresh()
        return result

    async def set_auto_unload(call: ServiceCall) -> dict:
        printer_id = int(call.data[ATTR_PRINTER_ID])
        mode = call.data.get(ATTR_MODE)
        coordinator = _coordinator_for(hass, printer_id)
        result = await _run_api_call(printer_id, coordinator.api.async_set_auto_unload(printer_id, mode))
        await coordinator.async_request_refresh()
        return result

    async def skip_parts(call: ServiceCall) -> dict:
        printer_id = int(call.data[ATTR_PRINTER_ID])
        names = [str(n) for n in call.data[ATTR_NAMES] if str(n).strip()]
        coordinator = _coordinator_for(hass, printer_id)
        result = await _run_api_call(printer_id, coordinator.api.async_skip_parts(printer_id, names))
        await coordinator.async_request_refresh()
        return result

    async def dismiss_notification(call: ServiceCall) -> dict:
        notification_id = int(call.data[ATTR_NOTIFICATION_ID])
        coordinator = _coordinator_for_notification(hass, notification_id)
        try:
            result = await coordinator.api.async_dismiss_notification(notification_id)
        except NotFound as err:
            raise ServiceValidationError(f"Plastic Slinger has no notification {notification_id}") from err
        except InvalidAuth as err:
            raise HomeAssistantError("The Plastic Slinger API key was rejected") from err
        except PlasticSlingerError as err:
            raise HomeAssistantError(f"Plastic Slinger command failed: {err}") from err
        coordinator.async_remove_dismissed_notification(notification_id)
        return {ATTR_NOTIFICATION_ID: notification_id, "dismissed": bool(result.get("dismissed", True))}

    async def dismiss_all_notifications(call: ServiceCall) -> dict:
        coordinator = _first_coordinator(hass)
        try:
            result = await coordinator.api.async_dismiss_all_notifications()
        except InvalidAuth as err:
            raise HomeAssistantError("The Plastic Slinger API key was rejected") from err
        except PlasticSlingerError as err:
            raise HomeAssistantError(f"Plastic Slinger command failed: {err}") from err
        coordinator.async_clear_all_notifications()
        return {"ok": True, "dismissed_count": int(result.get("dismissed_count", 0))}

    for name, handler, schema in (
        (SERVICE_DISMISS_PRINT, dismiss_print, PRINTER_ID_SCHEMA),
        (SERVICE_PAUSE_PRINT, pause_print, PRINTER_ID_SCHEMA),
        (SERVICE_RESUME_PRINT, resume_print, PRINTER_ID_SCHEMA),
        (SERVICE_CANCEL_PRINT, cancel_print, PRINTER_ID_SCHEMA),
        (SERVICE_SET_LIGHT, set_light, SET_LIGHT_SCHEMA),
        (SERVICE_SET_AUTO_UNLOAD, set_auto_unload, SET_AUTO_UNLOAD_SCHEMA),
        (SERVICE_SKIP_PARTS, skip_parts, SKIP_PARTS_SCHEMA),
        (SERVICE_DISMISS_NOTIFICATION, dismiss_notification, NOTIFICATION_ID_SCHEMA),
        (SERVICE_DISMISS_ALL_NOTIFICATIONS, dismiss_all_notifications, EMPTY_SCHEMA),
    ):
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            schema=schema,
            supports_response=SupportsResponse.OPTIONAL,
        )


async def _run_api_call(printer_id: int, coro) -> dict:
    try:
        return await coro
    except NotFound as err:
        raise ServiceValidationError(f"Plastic Slinger has no printer {printer_id}") from err
    except InvalidAuth as err:
        raise HomeAssistantError("The Plastic Slinger API key was rejected") from err
    except PlasticSlingerError as err:
        raise HomeAssistantError(f"Plastic Slinger command failed: {err}") from err


def _first_coordinator(hass: HomeAssistant) -> PlasticSlingerCoordinator:
    coordinators: list[PlasticSlingerCoordinator] = [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if not coordinators:
        raise ServiceValidationError("Plastic Slinger isn't set up")
    return coordinators[0]


def _coordinator_for(hass: HomeAssistant, printer_id: int) -> PlasticSlingerCoordinator:
    """The loaded entry that has this printer on its glance list, else the first loaded entry."""
    coordinators: list[PlasticSlingerCoordinator] = [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if not coordinators:
        raise ServiceValidationError("Plastic Slinger isn't set up")
    for coordinator in coordinators:
        if coordinator.has_printer(printer_id):
            return coordinator
    return coordinators[0]


def _coordinator_for_notification(hass: HomeAssistant, notification_id: int) -> PlasticSlingerCoordinator:
    """The loaded entry that has this notification on its feed, else the first loaded entry."""
    coordinators: list[PlasticSlingerCoordinator] = [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if not coordinators:
        raise ServiceValidationError("Plastic Slinger isn't set up")
    for coordinator in coordinators:
        if coordinator.has_notification(notification_id):
            return coordinator
    return coordinators[0]
