"""Client for the Plastic Slinger service's /api/v1 API."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import API_PREFIX


class PlasticSlingerError(Exception):
    """Base error."""


class CannotConnect(PlasticSlingerError):
    """The service could not be reached or returned an error."""


class InvalidAuth(PlasticSlingerError):
    """The API key was rejected."""


class NotFound(PlasticSlingerError):
    """The requested printer or snapshot was not found."""


class PlasticSlingerApi:
    """Reads active prints and camera snapshots, and runs printer control commands.
    Authenticates with an API key created in Plastic Slinger (Settings -> API keys).
    """

    def __init__(self, session: aiohttp.ClientSession, url: str, api_key: str) -> None:
        self._session = session
        self._url = normalize_url(url)
        self._api_key = api_key

    async def async_get_glance(self) -> dict[str, Any]:
        """Active, paused, recently completed, and failed printers plus status colors and sort mode."""
        return await self._request_json("GET", "/glance")

    async def async_dismiss_print(self, printer_id: int) -> dict[str, Any]:
        """Clears a held completed or failed print from the glance list."""
        return await self._request_json("POST", f"/glance/{int(printer_id)}/dismiss")

    async def async_pause_print(self, printer_id: int) -> dict[str, Any]:
        """Pauses the active print on a printer."""
        return await self._request_json("POST", f"/printers/{int(printer_id)}/pause")

    async def async_resume_print(self, printer_id: int) -> dict[str, Any]:
        """Resumes a paused print on a printer."""
        return await self._request_json("POST", f"/printers/{int(printer_id)}/resume")

    async def async_cancel_print(self, printer_id: int) -> dict[str, Any]:
        """Cancels the active or paused print on a printer."""
        return await self._request_json("POST", f"/printers/{int(printer_id)}/cancel")

    async def async_set_light(self, printer_id: int, on: bool | None = None) -> dict[str, Any]:
        """Sets or toggles the chamber light on a printer."""
        body: dict[str, Any] = {} if on is None else {"on": bool(on)}
        return await self._request_json("POST", f"/printers/{int(printer_id)}/light", body)

    async def async_set_auto_unload(self, printer_id: int, mode: str | None = None) -> dict[str, Any]:
        """Sets or cycles the auto-unload-after-print mode ('off', 'once', 'always')."""
        body: dict[str, Any] = {} if not mode else {"mode": str(mode)}
        return await self._request_json("POST", f"/printers/{int(printer_id)}/auto-unload", body)

    async def async_skip_parts(self, printer_id: int, names: list[str]) -> dict[str, Any]:
        """Skips one or more parts (EXCLUDE_OBJECT) on a Moonraker printer mid-print."""
        return await self._request_json(
            "POST", f"/printers/{int(printer_id)}/skip-parts", {"names": list(names)}
        )

    async def async_get_notifications(
        self, include_dismissed: bool = False, limit: int = 50
    ) -> dict[str, Any]:
        """Active visual notifications plus severity counts and status colors."""
        inc = "true" if include_dismissed else "false"
        return await self._request_json(
            "GET", f"/notifications?include_dismissed={inc}&limit={int(limit)}"
        )

    async def async_dismiss_notification(self, notification_id: int) -> dict[str, Any]:
        """Dismisses a single visual notification by ID."""
        return await self._request_json("POST", f"/notifications/{int(notification_id)}/dismiss")

    async def async_dismiss_all_notifications(self) -> dict[str, Any]:
        """Dismisses all active visual notifications."""
        return await self._request_json("POST", "/notifications/dismiss-all")

    async def async_get_notification_image(self, notification_id: int) -> tuple[bytes, str]:
        """Fetches the image attached to a notification (camera snapshot, PrintGuard frame, or thumbnail)."""
        path = f"/notifications/{int(notification_id)}/image"
        try:
            async with asyncio.timeout(15), self._session.get(
                f"{self._url}{API_PREFIX}{path}",
                headers={"Authorization": f"Bearer {self._api_key}", "Accept": "image/*"},
            ) as response:
                if response.status == 401:
                    raise InvalidAuth("The API key was rejected")
                if response.status == 404:
                    raise NotFound(f"HTTP 404 from {path}")
                if response.status != 200:
                    raise CannotConnect(f"HTTP {response.status} from {path}")
                content_type = response.headers.get("Content-Type", "image/jpeg")
                return await response.read(), content_type
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect(str(err) or err.__class__.__name__) from err

    async def async_get_snapshot(self, printer_id: int) -> tuple[bytes, str]:
        """Fetches the printer's JPEG snapshot (or held last frame when powered off)."""
        path = f"/printers/{int(printer_id)}/snapshot"
        try:
            async with asyncio.timeout(15), self._session.get(
                f"{self._url}{API_PREFIX}{path}",
                headers={"Authorization": f"Bearer {self._api_key}", "Accept": "image/*"},
            ) as response:
                if response.status == 401:
                    raise InvalidAuth("The API key was rejected")
                if response.status == 404:
                    raise NotFound(f"HTTP 404 from {path}")
                if response.status != 200:
                    raise CannotConnect(f"HTTP {response.status} from {path}")
                content_type = response.headers.get("Content-Type", "image/jpeg")
                return await response.read(), content_type
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect(str(err) or err.__class__.__name__) from err

    async def _request_json(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            async with asyncio.timeout(15), self._session.request(
                method,
                f"{self._url}{API_PREFIX}{path}",
                headers={"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"},
                json=body,
            ) as response:
                if response.status == 401:
                    raise InvalidAuth("The API key was rejected")
                if response.status == 404:
                    raise NotFound(f"HTTP 404 from {path}")
                if response.status != 200:
                    try:
                        err_json = await response.json()
                        err_msg = err_json.get("error") or err_json.get("message")
                    except Exception:
                        err_msg = None
                    raise CannotConnect(err_msg or f"HTTP {response.status} from {path}")
                return await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise CannotConnect(str(err) or err.__class__.__name__) from err


def normalize_url(url: str) -> str:
    """'http://plasticslinger.example.lan:6060/' -> 'http://plasticslinger.example.lan:6060'."""
    return url.strip().rstrip("/")
