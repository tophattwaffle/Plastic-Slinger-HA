"""Config flow, sensor, snapshot proxy view, and printer control actions against a mocked Plastic Slinger service."""

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.plastic_slinger.const import CONF_SCAN_INTERVAL, CONF_VERIFY_SSL, DOMAIN

from .conftest import API_KEY, DEFAULT_STATUS_COLORS, URL, mock_service, printer_tile

PRINTERS = [
    printer_tile(3, "PrinterA", status="printing", progress=48, remaining_seconds=1800, can_dismiss=False),
    printer_tile(5, "PrinterB", status="complete", progress=100, remaining_seconds=0, can_dismiss=True, is_powered_off=True),
]


async def _setup(hass: HomeAssistant, aioclient_mock, printers=PRINTERS) -> MockConfigEntry:
    mock_service(aioclient_mock, printers)
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=URL, data={CONF_URL: URL, CONF_API_KEY: API_KEY, CONF_VERIFY_SSL: True}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow_creates_entry(hass: HomeAssistant, aioclient_mock) -> None:
    mock_service(aioclient_mock, PRINTERS)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL + "/", CONF_API_KEY: API_KEY, CONF_VERIFY_SSL: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_URL] == URL
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == f"Bearer {API_KEY}"


async def test_config_flow_reports_bad_key_and_unreachable(hass: HomeAssistant, aioclient_mock) -> None:
    mock_service(aioclient_mock, PRINTERS, status=401)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL, CONF_API_KEY: "ps_bad", CONF_VERIFY_SSL: True}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    mock_service(aioclient_mock, PRINTERS, status=500)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: URL, CONF_API_KEY: API_KEY, CONF_VERIFY_SSL: True}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_sensor_attributes_and_unrecorded_keys(hass: HomeAssistant, aioclient_mock) -> None:
    await _setup(hass, aioclient_mock)

    state = hass.states.get("sensor.plastic_slinger_active_prints")
    assert state is not None
    assert state.state == "2"
    assert state.attributes["printing_count"] == 1
    assert state.attributes["complete_count"] == 1
    assert state.attributes["status_colors"] == DEFAULT_STATUS_COLORS
    assert [p["id"] for p in state.attributes["printers"]] == [3, 5]

    entity = hass.data["entity_components"]["sensor"].get_entity("sensor.plastic_slinger_active_prints")
    assert "printers" in entity._unrecorded_attributes
    assert "status_colors" in entity._unrecorded_attributes


async def test_dismiss_print_removes_printer_immediately(hass: HomeAssistant, aioclient_mock) -> None:
    await _setup(hass, aioclient_mock)
    aioclient_mock.post(f"{URL}/api/v1/glance/5/dismiss", json={"printer_id": 5, "dismissed": True})

    response = await hass.services.async_call(
        DOMAIN, "dismiss_print", {"printer_id": 5}, blocking=True, return_response=True
    )
    assert response == {"printer_id": 5, "dismissed": True}

    state = hass.states.get("sensor.plastic_slinger_active_prints")
    assert state.state == "1"
    assert [p["id"] for p in state.attributes["printers"]] == [3]
    assert state.attributes["complete_count"] == 0


async def test_dismiss_print_reports_unknown_printer(hass: HomeAssistant, aioclient_mock) -> None:
    await _setup(hass, aioclient_mock)
    aioclient_mock.post(f"{URL}/api/v1/glance/999/dismiss", status=404)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "dismiss_print", {"printer_id": 999}, blocking=True)


async def test_printer_control_services_call_api_and_refresh(hass: HomeAssistant, aioclient_mock) -> None:
    await _setup(hass, aioclient_mock)
    aioclient_mock.post(f"{URL}/api/v1/printers/3/pause", json={"printer_id": 3, "action": "pause", "success": True})
    aioclient_mock.post(f"{URL}/api/v1/printers/3/resume", json={"printer_id": 3, "action": "resume", "success": True})
    aioclient_mock.post(f"{URL}/api/v1/printers/3/cancel", json={"printer_id": 3, "action": "cancel", "success": True})
    aioclient_mock.post(f"{URL}/api/v1/printers/3/light", json={"printer_id": 3, "action": "light", "success": True, "chamber_light_on": True})
    aioclient_mock.post(f"{URL}/api/v1/printers/3/auto-unload", json={"printer_id": 3, "action": "auto_unload", "success": True, "auto_unload_mode": "once"})
    aioclient_mock.post(f"{URL}/api/v1/printers/3/skip-parts", json={"printer_id": 3, "action": "skip_parts", "success": True})

    res_pause = await hass.services.async_call(
        DOMAIN, "pause_print", {"printer_id": 3}, blocking=True, return_response=True
    )
    assert res_pause["success"] is True

    res_resume = await hass.services.async_call(
        DOMAIN, "resume_print", {"printer_id": 3}, blocking=True, return_response=True
    )
    assert res_resume["success"] is True

    res_light = await hass.services.async_call(
        DOMAIN, "set_light", {"printer_id": 3, "on": True}, blocking=True, return_response=True
    )
    assert res_light["chamber_light_on"] is True

    res_unload = await hass.services.async_call(
        DOMAIN, "set_auto_unload", {"printer_id": 3, "mode": "once"}, blocking=True, return_response=True
    )
    assert res_unload["auto_unload_mode"] == "once"

    res_skip = await hass.services.async_call(
        DOMAIN, "skip_parts", {"printer_id": 3, "names": ["Part_1"]}, blocking=True, return_response=True
    )
    assert res_skip["success"] is True

    res_cancel = await hass.services.async_call(
        DOMAIN, "cancel_print", {"printer_id": 3}, blocking=True, return_response=True
    )
    assert res_cancel["success"] is True


async def test_snapshot_proxy_view_serves_jpeg(hass: HomeAssistant, aioclient_mock, hass_client) -> None:
    await _setup(hass, aioclient_mock)
    jpeg_bytes = b"\xff\xd8\x42\x99\xff\xd9"
    aioclient_mock.get(f"{URL}/api/v1/printers/3/snapshot", content=jpeg_bytes, headers={"Content-Type": "image/jpeg"})

    client = await hass_client()
    resp = await client.get("/api/plastic_slinger/snapshot/3")
    assert resp.status == 200
    assert resp.headers.get("Content-Type") == "image/jpeg"
    assert await resp.read() == jpeg_bytes


async def test_rejected_key_starts_reauth(hass: HomeAssistant, aioclient_mock) -> None:
    entry = await _setup(hass, aioclient_mock)
    mock_service(aioclient_mock, PRINTERS, status=401)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    flows = [f for f in hass.config_entries.flow.async_progress() if f["context"]["source"] == config_entries.SOURCE_REAUTH]
    assert len(flows) == 1

    mock_service(aioclient_mock, PRINTERS)
    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {CONF_API_KEY: "ps_new"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "ps_new"


async def test_options_set_polling_interval_in_place(hass: HomeAssistant, aioclient_mock) -> None:
    entry = await _setup(hass, aioclient_mock)
    coordinator = entry.runtime_data
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_SCAN_INTERVAL: 15})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data is coordinator
    assert coordinator.update_interval.total_seconds() == 15


async def test_brief_outage_keeps_last_data_then_goes_unavailable(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    entry = await _setup(hass, aioclient_mock)
    mock_service(aioclient_mock, PRINTERS, status=503)

    freezer.tick(30)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get("sensor.plastic_slinger_active_prints")
    assert state.state == "2"

    freezer.tick(200)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.plastic_slinger_active_prints").state == "unavailable"
