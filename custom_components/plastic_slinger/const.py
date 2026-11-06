"""Constants for the Plastic Slinger integration."""

from datetime import timedelta

DOMAIN = "plastic_slinger"

CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"

# Home Assistant talks to Plastic Slinger on the LAN, so polling every 5 s is cheap.
DEFAULT_SCAN_INTERVAL = 5
MIN_SCAN_INTERVAL = 2
MAX_SCAN_INTERVAL = 300

# Keep showing the last data while the service is briefly unreachable (e.g. restarting after a deploy).
STALE_DATA_GRACE = timedelta(minutes=2)

API_PREFIX = "/api/v1"

SERVICE_DISMISS_PRINT = "dismiss_print"
SERVICE_PAUSE_PRINT = "pause_print"
SERVICE_RESUME_PRINT = "resume_print"
SERVICE_CANCEL_PRINT = "cancel_print"
SERVICE_SET_LIGHT = "set_light"
SERVICE_SET_AUTO_UNLOAD = "set_auto_unload"
SERVICE_SKIP_PARTS = "skip_parts"

ATTR_PRINTER_ID = "printer_id"
ATTR_ON = "on"
ATTR_MODE = "mode"
ATTR_NAMES = "names"


def scan_interval(options: dict) -> timedelta:
    """The polling interval from the entry options, clamped to the allowed range."""
    seconds = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        seconds = DEFAULT_SCAN_INTERVAL
    return timedelta(seconds=max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, seconds)))
