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
    """Reads active prints and camera snapshots, and clears finished prints from the glance view.
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
                    raise CannotConnect(f"HTTP {response.status} from {path}")
                return await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise CannotConnect(str(err) or err.__class__.__name__) from err


def normalize_url(url: str) -> str:
    """'http://plasticslinger.example.lan:6060/' -> 'http://plasticslinger.example.lan:6060'."""
    return url.strip().rstrip("/")
