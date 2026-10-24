"""Compatibility reports must not expose identity or credentials."""
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.desloc.api import (
    Device, DeslocCommandTimeout, DeslocConnectionError, DeslocRateLimitError,
    DeslocProtocolError, DeslocClockError, DeslocError,
)
from custom_components.desloc.coordinator import DeslocCoordinator
from custom_components.desloc.diagnostics import async_get_config_entry_diagnostics
from custom_components.desloc.entity import DeslocEntity


@pytest.mark.parametrize("model,validation", [("C100 Plus", "tested"), ("D110 Plus", "experimental")])
async def test_allowlisted_diagnostics(hass, entry, row, model, validation):
    device = Device.from_json(dict(row, model=model, deviceName="private door name"))
    entry.runtime_data = SimpleNamespace(data=device, last_update_success=True)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["device"]["model"] == model
    assert result["device"]["model_validation"] == validation
    assert result["last_poll_success"] is True
    encoded = json.dumps(result)
    for private_value in ("test-secret", "test-phone", "001122334455", "00:11:22:33:44:55",
                          "private door name", entry.entry_id):
        assert private_value not in encoded
    assert not {"id", "mac", "name", "credentials", "token", "pin"} & result["device"].keys()


async def test_unloaded_diagnostics(hass, entry):
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result == {"last_poll_success": False, "device_present": False, "device": None, "command": None}


async def test_unknown_model_is_visible_but_not_claimed_tested(hass, entry, row):
    coordinator = DeslocCoordinator(hass, entry, AsyncMock())
    coordinator.async_set_updated_data(Device.from_json(dict(row, model="D110 Plus")))
    entity = DeslocEntity(coordinator, "lock")
    assert entity.device_info["model"] == "D110 Plus"
    assert entity.extra_state_attributes == {"model_validation": "experimental"}
    await coordinator.async_shutdown()


async def test_command_diagnostics_and_logs_exclude_private_command_data(hass, entry, row, caplog):
    """Only fixed categories/counts appear, even when exceptions carry secrets."""
    caplog.set_level(logging.DEBUG, logger="custom_components.desloc.coordinator")
    private_values = ["test-secret", "test-phone", "001122334455", "00:11:22:33:44:55",
                      "private door name", entry.entry_id, "private-command-id", "825194"]
    api = AsyncMock()
    api.async_switch_lock.return_value = "private-command-id"
    api.async_command_complete.side_effect = DeslocCommandTimeout(" ".join(private_values))
    coordinator = DeslocCoordinator(hass, entry, api)
    entry.runtime_data = coordinator
    coordinator.async_set_updated_data(Device.from_json(dict(row, deviceName="private door name")))
    with patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=RuntimeError(" ".join(private_values)))), \
            pytest.raises(HomeAssistantError):
        await coordinator.async_set_locked(False)
    result = await async_get_config_entry_diagnostics(hass, entry)
    snapshot = result["command"]
    assert set(snapshot) == {
        "phase", "outcome", "elapsed_seconds", "result_poll_count", "accepted",
        "acknowledged", "post_expiry_refresh", "awaiting_fresh_state", "error_kind",
        "result_expired", "state_confirmed", "state_poll_count",
    }
    assert snapshot["phase"] == "reconciling_state"
    assert snapshot["outcome"] == "result_expired"
    assert snapshot["accepted"] is True
    assert snapshot["acknowledged"] is False
    assert snapshot["result_poll_count"] == 1
    assert snapshot["awaiting_fresh_state"] is True
    assert snapshot["post_expiry_refresh"] == "failed"
    assert snapshot["error_kind"] == "unknown_error"
    assert snapshot["result_expired"] is True
    assert snapshot["state_confirmed"] is False
    assert snapshot["state_poll_count"] == 1
    diagnostic_and_log = json.dumps(result) + "\n" + caplog.text
    for private_value in private_values:
        assert private_value not in diagnostic_and_log
    assert "outcome=result_expired" in caplog.text
    assert "phase=reconciling_state" in caplog.text
    assert "accepted=True" in caplog.text
    assert "acknowledged=False" in caplog.text
    # Callers cannot overwrite the coordinator's retained record.
    snapshot["outcome"] = "tampered"
    assert coordinator.command_diagnostics["outcome"] == "result_expired"
    coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=1,
        doorStateUpdateTime=row["doorStateUpdateTime"] + 1000)))
    recovered = await async_get_config_entry_diagnostics(hass, entry)
    assert recovered["command"]["awaiting_fresh_state"] is False
    assert recovered["command"]["outcome"] == "result_expired"
    assert coordinator.is_locked is False
    await coordinator.async_shutdown()


@pytest.mark.parametrize("failure,error_kind", [
    (DeslocConnectionError("private-network-error"), "connection_error"),
    (DeslocRateLimitError("private-limit-error"), "rate_limited"),
    (DeslocProtocolError("private-protocol-error"), "protocol_error"),
    (DeslocClockError("private-clock-error"), "clock_error"),
    (DeslocError("private-unknown-error"), "unknown_api_error"),
])
async def test_failed_command_exposes_safe_error_category_without_raw_details(
    hass, entry, row, caplog, failure, error_kind,
):
    caplog.set_level(logging.DEBUG, logger="custom_components.desloc.coordinator")
    api = AsyncMock()
    api.async_switch_lock.side_effect = failure
    coordinator = DeslocCoordinator(hass, entry, api)
    entry.runtime_data = coordinator
    coordinator.async_set_updated_data(Device.from_json(row))
    with pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    assert error.value.translation_key == "command_failed"
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["command"]["phase"] == "sending"
    assert result["command"]["outcome"] == "failed"
    assert result["command"]["error_kind"] == error_kind
    assert result["command"]["accepted"] is False
    assert result["command"]["result_poll_count"] == 0
    assert "private-" not in json.dumps(result) + caplog.text
    assert f"error_kind={error_kind}" in caplog.text
    api.async_switch_lock.assert_awaited_once()
    api.async_command_complete.assert_not_awaited()
    await coordinator.async_shutdown()


async def test_command_diagnostics_track_pending_and_freeze_completed_elapsed_time(hass, entry, row):
    api = AsyncMock()
    api.async_switch_lock.return_value = "private-command-id"
    coordinator = DeslocCoordinator(hass, entry, api)
    entry.runtime_data = coordinator
    coordinator.async_set_updated_data(Device.from_json(row))
    initial = coordinator.command_diagnostics
    assert initial["outcome"] == "not_started"
    assert initial["phase"] == "idle"
    assert initial["elapsed_seconds"] == 0
    assert initial["awaiting_fresh_state"] is False
    clock = SimpleNamespace(value=10.0)
    clock.monotonic = lambda: clock.value

    async def result(_command_id):
        clock.value = 11.2344
        snapshot = coordinator.command_diagnostics
        assert snapshot["outcome"] == "pending"
        assert snapshot["phase"] == "waiting_result"
        assert snapshot["elapsed_seconds"] == 1.234
        assert snapshot["accepted"] is True
        assert snapshot["acknowledged"] is False
        return True

    async def refresh():
        assert coordinator.command_diagnostics["phase"] == "confirming_state"
        assert coordinator.command_diagnostics["acknowledged"] is True
        clock.value = 12.3454
        coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=1,
            doorStateUpdateTime=row["doorStateUpdateTime"] + 1000)))

    api.async_command_complete.side_effect = result
    with patch("custom_components.desloc.coordinator.time", clock), \
            patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=refresh)):
        await coordinator.async_set_locked(False)
        clock.value = 1000
        snapshot = coordinator.command_diagnostics
    assert snapshot["outcome"] == "confirmed"
    assert snapshot["elapsed_seconds"] == 2.345
    assert snapshot["awaiting_fresh_state"] is False
    assert snapshot["post_expiry_refresh"] == "not_attempted"
    assert snapshot["state_poll_count"] == 1
    assert snapshot["state_confirmed"] is True
    assert snapshot["result_expired"] is False
    await coordinator.async_shutdown()


async def test_late_confirmation_retains_expiry_without_fabricating_acknowledgement(
    hass, entry, row, caplog,
):
    """A later successful state observation is evidence distinct from the result."""
    caplog.set_level(logging.DEBUG, logger="custom_components.desloc.coordinator")
    private_values = ["private-command-id", "private-result-token", "private door name", "825194"]
    api = AsyncMock()
    api.async_switch_lock.return_value = private_values[0]
    coordinator = DeslocCoordinator(hass, entry, api)
    entry.runtime_data = coordinator
    coordinator.async_set_updated_data(Device.from_json(dict(row, deviceName=private_values[2])))
    clock = SimpleNamespace(value=100.0)
    clock.monotonic = lambda: clock.value

    async def expire(_command_id):
        clock.value = 111.0
        raise DeslocCommandTimeout(" ".join(private_values))

    async def refresh():
        pending = coordinator.command_diagnostics
        assert pending["phase"] == "reconciling_state"
        assert pending["accepted"] is True
        assert pending["result_expired"] is True
        assert pending["acknowledged"] is False
        assert pending["state_confirmed"] is False
        clock.value = 124.0
        coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=1,
            doorStateUpdateTime=row["doorStateUpdateTime"] + 1000)))

    api.async_command_complete.side_effect = expire
    with patch("custom_components.desloc.coordinator.time", clock), \
            patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=refresh)):
        await coordinator.async_set_locked(False)
        clock.value = 171.0
        result = await async_get_config_entry_diagnostics(hass, entry)
    snapshot = result["command"]
    assert snapshot["outcome"] == "state_confirmed_after_expiry"
    assert snapshot["elapsed_seconds"] == 24.0, "elapsed time freezes when the attempt finishes"
    assert snapshot["result_expired"] is True
    assert snapshot["state_confirmed"] is True
    assert snapshot["acknowledged"] is False
    assert snapshot["result_poll_count"] == 1
    assert snapshot["state_poll_count"] == 1
    assert snapshot["post_expiry_refresh"] == "success"
    assert snapshot["awaiting_fresh_state"] is False
    encoded = json.dumps(result) + caplog.text
    for value in private_values + [entry.entry_id, "test-secret", "test-phone", "001122334455"]:
        assert value not in encoded
    assert "result_expired=True" in caplog.text
    assert "state_confirmed=True" in caplog.text
    assert "acknowledged=False" in caplog.text
    snapshot["result_expired"] = False
    assert coordinator.command_diagnostics["result_expired"] is True
    await coordinator.async_shutdown()
