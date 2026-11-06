"""Authenticated Home Assistant HTTP view that proxies printer camera snapshots from Plastic Slinger."""

from __future__ import annotations

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .api import NotFound, PlasticSlingerError
from .const import DOMAIN
from .coordinator import PlasticSlingerCoordinator


class PlasticSlingerSnapshotView(HomeAssistantView):
    """Proxies GET /api/v1/printers/{printer_id}/snapshot through Home Assistant's authenticated HTTP pipeline."""

    url = "/api/plastic_slinger/snapshot/{printer_id}"
    name = "api:plastic_slinger:snapshot"
    requires_auth = True

    async def get(self, request: web.Request, printer_id: str) -> web.Response:
        try:
            pid = int(printer_id)
        except (TypeError, ValueError):
            return web.Response(status=400, text="Invalid printer_id")

        hass: HomeAssistant = request.app["hass"]
        coordinator = _coordinator_for_printer(hass, pid)
        if coordinator is None:
            return web.Response(status=503, text="Plastic Slinger is not loaded")

        try:
            body, content_type = await coordinator.api.async_get_snapshot(pid)
        except NotFound:
            return web.Response(status=404, text="Snapshot unavailable")
        except PlasticSlingerError as err:
            return web.Response(status=502, text=f"Upstream snapshot error: {err}")

        return web.Response(
            body=body,
            content_type=content_type.split(";")[0].strip() or "image/jpeg",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )


def _coordinator_for_printer(hass: HomeAssistant, printer_id: int) -> PlasticSlingerCoordinator | None:
    coordinators: list[PlasticSlingerCoordinator] = [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if not coordinators:
        return None
    for coordinator in coordinators:
        if coordinator.has_printer(printer_id):
            return coordinator
    return coordinators[0]
