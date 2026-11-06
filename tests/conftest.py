"""Fixtures and a mocked Plastic Slinger service."""

import sys

import pytest

if sys.platform == "win32":
    import asyncio

    import pytest_socket
    from homeassistant import runner

    pytest_socket.disable_socket = lambda *args, **kwargs: None
    if hasattr(runner, "HassEventLoopPolicy"):
        runner.HassEventLoopPolicy._loop_factory = asyncio.SelectorEventLoop
    elif hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

URL = "http://plasticslinger.example.lan:6060"
API_KEY = "ps_testkey"

DEFAULT_STATUS_COLORS = {
    "printing": "#8b4ce8",
    "complete": "#1ca87a",
    "paused": "#f37920",
    "failed": "#e3342a",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load integrations from custom_components."""
    yield


def printer_tile(
    printer_id: int,
    name: str,
    status: str = "printing",
    progress: int = 50,
    remaining_seconds: int | None = 1800,
    can_dismiss: bool = False,
    is_powered_off: bool = False,
) -> dict:
    labels = {
        "printing": "PRINTING",
        "complete": "COMPLETE",
        "paused": "PAUSED",
        "failed": "FAILED",
    }
    return {
        "id": printer_id,
        "name": name,
        "machine_type": "CoreXY",
        "status": status,
        "status_label": labels.get(status, status.upper()),
        "progress_percent": progress,
        "remaining_seconds": remaining_seconds,
        "sub_text": "30m left" if status == "printing" else "Done 5m ago",
        "file_name": "Part.gcode",
        "is_powered_off": is_powered_off,
        "can_dismiss": can_dismiss,
        "ended_at_ts": 1762389280 if status in ("complete", "failed") else None,
        "camera_rotation": 0,
        "camera_flip_h": False,
        "camera_flip_v": False,
    }


def glance_payload(
    printers: list[dict],
    sort_mode: str = "Default",
    status_colors: dict | None = None,
) -> dict:
    return {
        "generated_at": 1762390000,
        "sort_mode": sort_mode,
        "status_colors": status_colors or DEFAULT_STATUS_COLORS,
        "active_count": len(printers),
        "printing_count": sum(1 for p in printers if p.get("status") == "printing"),
        "paused_count": sum(1 for p in printers if p.get("status") == "paused"),
        "complete_count": sum(1 for p in printers if p.get("status") == "complete"),
        "failed_count": sum(1 for p in printers if p.get("status") == "failed"),
        "printers": printers,
    }


def mock_service(aioclient_mock, printers: list[dict], status: int = 200, status_colors: dict | None = None) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{URL}/api/v1/glance",
        status=status,
        json=glance_payload(printers, status_colors=status_colors),
    )
