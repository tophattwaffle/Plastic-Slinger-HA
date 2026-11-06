"""The dismiss_print action: clears a finished or failed print from the glance view."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .api import InvalidAuth, NotFound, PlasticSlingerError
from .const import ATTR_PRINTER_ID, DOMAIN, SERVICE_DISMISS_PRINT
from .coordinator import PlasticSlingerCoordinator

DISMISS_PRINT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PRINTER_ID): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions (once, for every config entry)."""

    async def dismiss_print(call: ServiceCall) -> dict:
        printer_id = int(call.data[ATTR_PRINTER_ID])
        coordinator = _coordinator_for(hass, printer_id)
        try:
            result = await coordinator.api.async_dismiss_print(printer_id)
        except NotFound as err:
            raise ServiceValidationError(
                f"Plastic Slinger has no printer {printer_id}"
            ) from err
        except InvalidAuth as err:
            raise HomeAssistantError("The Plastic Slinger API key was rejected") from err
        except PlasticSlingerError as err:
            raise HomeAssistantError(f"Can't reach Plastic Slinger: {err}") from err

        coordinator.async_remove_dismissed_printer(printer_id)
        return {ATTR_PRINTER_ID: printer_id, "dismissed": bool(result.get("dismissed", True))}

    hass.services.async_register(
        DOMAIN,
        SERVICE_DISMISS_PRINT,
        dismiss_print,
        schema=DISMISS_PRINT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


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
