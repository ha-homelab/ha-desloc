"""No physical commands: command and cloud responses are synthetic."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from custom_components.desloc.account import DeslocAccount
from custom_components.desloc.api import Device, DeslocConnectionError, DeslocCommandTimeout
from custom_components.desloc.coordinator import DeslocCoordinator

async def test_pending_result_then_fresh_state(hass, entry, row):
    api = AsyncMock()
    api.async_switch_lock.return_value = "test-command"
    api.async_command_complete.side_effect = [False, False, True]
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=1)))

    async def refresh():
        assert coordinator.pending_target is True
        coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=2,
            doorStateUpdateTime=row["doorStateUpdateTime"] + 1000)))

    with patch.object(coordinator, "async_refresh", new=refresh), patch(
        "custom_components.desloc.coordinator.asyncio.sleep", new=AsyncMock()
    ):
        await coordinator.async_set_locked(True)
    api.async_switch_lock.assert_awaited_once_with(123, unlock=False)
    assert api.async_command_complete.await_count == 3
    assert coordinator.is_locked is True
    assert coordinator.pending_target is None
    await coordinator.async_shutdown()


@pytest.mark.parametrize("failure", [DeslocConnectionError("Connection lost"), DeslocCommandTimeout("Expired")])
async def test_failure_leaves_old_state_unknown_without_retry(hass, entry, row, failure):
    api = AsyncMock()
    api.async_switch_lock.side_effect = failure
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    with patch.object(coordinator, "async_refresh", new=AsyncMock()), pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    assert error.value.translation_domain == "desloc"
    expected = "command_timeout" if isinstance(failure, DeslocCommandTimeout) else "command_failed"
    assert error.value.translation_key == expected
    api.async_switch_lock.assert_awaited_once_with(123, unlock=True)
    assert coordinator.is_locked is None
    assert coordinator.pending_target is None
    coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=1,
        doorStateUpdateTime=row["doorStateUpdateTime"] + 1000)))
    assert coordinator.is_locked is False
    await coordinator.async_shutdown()


async def test_acknowledgement_alone_does_not_confirm_bolt_state(hass, entry, row):
    api = AsyncMock()
    api.async_command_complete.return_value = True
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    with patch.object(coordinator, "async_refresh", new=AsyncMock()), patch(
        "custom_components.desloc.coordinator.asyncio.sleep", new=AsyncMock()
    ), pytest.raises(HomeAssistantError, match="not confirmed") as error:
        await coordinator.async_set_locked(True)
    assert error.value.translation_domain == "desloc"
    assert error.value.translation_key == "command_unconfirmed"
    api.async_switch_lock.assert_awaited_once()
    assert coordinator.is_locked is None
    await coordinator.async_shutdown()


async def test_busy_command_rejected(hass, entry, row):
    api = AsyncMock()
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    async with coordinator._command_lock:
        with pytest.raises(HomeAssistantError, match="already in progress") as error:
            await coordinator.async_set_locked(False)
    assert error.value.translation_key == "command_in_progress"
    api.async_switch_lock.assert_not_called()
    await coordinator.async_shutdown()

async def test_unavailable_status_blocks_command_without_api_call(hass, entry, row):
    """No lock mutation when coordinator has no confirmed device status."""
    api = AsyncMock()
    coordinator = DeslocCoordinator(hass, entry, api)
    assert coordinator.data is None
    with pytest.raises(HomeAssistantError, match="status is unavailable") as error:
        await coordinator.async_set_locked(True)
    assert error.value.translation_key == "unavailable"
    api.async_switch_lock.assert_not_called()
    await coordinator.async_shutdown()


async def test_command_confirmation_bypasses_shared_account_snapshot(hass, entry, row):
    dr.async_setup(hass)
    await dr.async_load(hass)
    original = Device.from_json(row)
    fresh = Device.from_json(dict(row, doorState=1, doorStateUpdateTime=original.door_state_updated_ms + 1000))
    api = Mock(
        raise_if_blocked=Mock(),
        async_devices=AsyncMock(side_effect=[[original], [fresh]]),
        async_switch_lock=AsyncMock(return_value="synthetic-command"),
        async_command_complete=AsyncMock(return_value=True),
    )
    account = DeslocAccount(api)
    coordinator = DeslocCoordinator(hass, entry, api, account=account)
    coordinator.async_set_updated_data((await account.async_devices())[0])
    await coordinator.async_set_locked(False)
    assert coordinator.is_locked is False
    assert api.async_devices.await_count == 2
    api.async_switch_lock.assert_awaited_once_with(123, unlock=True)
    await coordinator.async_shutdown()
    await account.async_close()


async def test_accepted_command_pending_then_vendor_expiry_reads_once(hass, entry, row, transport):
    """Exercise real API decoding of 2206/2104 without any network or replay."""
    dr.async_setup(hass)
    await dr.async_load(hass)
    api, session, response, _ = transport
    response.json.side_effect = [
        {"status": 200, "success": True, "data": {"commandId": "private-command-id"}},
        {"status": 2206, "success": False},
        {"status": 2104, "success": False, "msg": "private-server-body"},
        {"status": 200, "success": True, "data": [row]},
    ]
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    with patch("custom_components.desloc.coordinator.asyncio.sleep", new=AsyncMock()), \
            pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    assert error.value.translation_key == "command_timeout"
    paths = [call.args[0] for call in session.post.call_args_list]
    assert sum(path.endswith("/remoteSwitchLock") for path in paths) == 1
    assert sum("/fecommand/result/" in path for path in paths) == 2
    assert sum(path.endswith("/api/device/list") for path in paths) == 1
    assert coordinator.is_locked is None
    assert coordinator.pending_target is None
    assert not coordinator._command_lock.locked()
    assert coordinator.command_diagnostics == {
        "phase": "waiting_result", "outcome": "result_expired",
        "elapsed_seconds": coordinator.command_diagnostics["elapsed_seconds"],
        "result_poll_count": 2, "accepted": True, "acknowledged": False,
        "post_expiry_refresh": "success", "awaiting_fresh_state": True, "error_kind": None,
    }
    assert coordinator.command_diagnostics["elapsed_seconds"] >= 0
    assert "private-server-body" not in str(error.value)
    await coordinator.async_shutdown()


@pytest.mark.parametrize("offset,expected", [(None, None), (-1000, None), (0, None), (1000, False)])
async def test_expiry_refresh_needs_a_new_bolt_timestamp(hass, entry, row, offset, expected):
    """Refresh may recover a fresh report but never rewrites the command result."""
    api = AsyncMock()
    api.async_switch_lock.return_value = "private-command-id"
    api.async_command_complete.side_effect = DeslocCommandTimeout("private-response")
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    timestamp = None if offset is None else row["doorStateUpdateTime"] + offset

    async def refresh():
        assert coordinator.pending_target is False
        coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=1,
            doorStateUpdateTime=timestamp)))

    with patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=refresh)) as reader, \
            pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    reader.assert_awaited_once()
    api.async_switch_lock.assert_awaited_once_with(123, unlock=True)
    api.async_command_complete.assert_awaited_once_with("private-command-id")
    assert error.value.translation_key == "command_timeout"
    assert coordinator.is_locked is expected
    assert coordinator.command_diagnostics["outcome"] == "result_expired"
    assert coordinator.command_diagnostics["awaiting_fresh_state"] is (expected is None)
    assert coordinator.pending_target is None
    await coordinator.async_shutdown()


@pytest.mark.parametrize("failure", [DeslocConnectionError("private-refresh-body"), RuntimeError("private-refresh-body")])
async def test_failed_post_expiry_read_preserves_original_error(hass, entry, row, failure):
    api = AsyncMock()
    api.async_command_complete.side_effect = DeslocCommandTimeout("private-result-body")
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    with patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=failure)) as reader, \
            pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    reader.assert_awaited_once()
    api.async_switch_lock.assert_awaited_once()
    assert error.value.translation_key == "command_timeout"
    assert "private-" not in str(error.value)
    assert coordinator.command_diagnostics["post_expiry_refresh"] == "failed"
    assert coordinator.command_diagnostics["outcome"] == "result_expired"
    assert coordinator.is_locked is None
    await coordinator.async_shutdown()


async def test_post_expiry_read_is_cancelled_by_its_bounded_timeout(hass, entry, row):
    api = AsyncMock()
    api.async_command_complete.side_effect = DeslocCommandTimeout("Expired")
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    cancelled = asyncio.Event()
    budgets = []
    actual_timeout = asyncio.timeout

    async def slow_refresh():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    def timeout(seconds):
        budgets.append(seconds)
        # Keep the real cancellation mechanism while shortening only the read.
        return actual_timeout(0.01 if len(budgets) == 2 else seconds)

    with patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=slow_refresh)) as reader, \
            patch("custom_components.desloc.coordinator.asyncio.timeout", side_effect=timeout), \
            pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    assert budgets[0] == 45
    assert 0 < budgets[1] <= 5
    assert cancelled.is_set()
    reader.assert_awaited_once()
    api.async_switch_lock.assert_awaited_once()
    assert error.value.translation_key == "command_timeout"
    assert coordinator.command_diagnostics["outcome"] == "result_expired"
    assert coordinator.command_diagnostics["post_expiry_refresh"] == "timed_out"
    assert coordinator.pending_target is None
    await coordinator.async_shutdown()


async def test_cancelling_post_expiry_read_propagates_and_releases_command(hass, entry, row):
    """An external cancellation must not become a timeout or trigger a replay."""
    api = AsyncMock()
    api.async_switch_lock.return_value = "private-command-id"
    api.async_command_complete.side_effect = DeslocCommandTimeout("Expired")
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    reading = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow_refresh():
        reading.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=slow_refresh)) as reader:
        command = asyncio.create_task(coordinator.async_set_locked(False))
        try:
            await asyncio.wait_for(reading.wait(), timeout=1)
            command.cancel()
            with pytest.raises(asyncio.CancelledError):
                await command
        finally:
            if not command.done():
                command.cancel()
                await asyncio.gather(command, return_exceptions=True)
    assert cancelled.is_set()
    reader.assert_awaited_once()
    api.async_switch_lock.assert_awaited_once_with(123, unlock=True)
    api.async_command_complete.assert_awaited_once_with("private-command-id")
    assert coordinator.command_diagnostics["outcome"] == "result_expired"
    assert coordinator.command_diagnostics["post_expiry_refresh"] == "cancelled"
    assert coordinator.pending_target is None
    assert not coordinator._command_lock.locked()
    assert coordinator.is_locked is None
    await coordinator.async_shutdown()


async def test_post_expiry_refresh_records_coordinator_fetch_failure(hass, entry, row):
    """DataUpdateCoordinator may retain a failure instead of raising it."""
    api = AsyncMock()
    api.async_command_complete.side_effect = DeslocCommandTimeout("Expired")
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))

    async def refresh():
        coordinator.last_update_success = False

    with patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=refresh)), \
            pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    assert error.value.translation_key == "command_timeout"
    assert coordinator.command_diagnostics["post_expiry_refresh"] == "failed"
    assert coordinator.command_diagnostics["outcome"] == "result_expired"
    api.async_switch_lock.assert_awaited_once()
    await coordinator.async_shutdown()


@pytest.mark.parametrize("elapsed,expected_budget", [(44.75, 0.25), (45, None), (46, None)])
async def test_post_expiry_read_respects_original_command_deadline(hass, entry, row, elapsed, expected_budget):
    api = AsyncMock()
    api.async_command_complete.side_effect = DeslocCommandTimeout("Expired")
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    clock = SimpleNamespace(monotonic=Mock(side_effect=[100.0, 100.0 + elapsed, 100.0 + elapsed]))
    actual_timeout = asyncio.timeout
    with patch("custom_components.desloc.coordinator.time", clock), \
            patch("custom_components.desloc.coordinator.asyncio.timeout", wraps=actual_timeout) as timer, \
            patch.object(coordinator, "async_refresh", new=AsyncMock()) as reader, \
            pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    assert error.value.translation_key == "command_timeout"
    if expected_budget is None:
        reader.assert_not_awaited()
        assert len(timer.call_args_list) == 1
        assert coordinator.command_diagnostics["post_expiry_refresh"] == "not_attempted"
    else:
        reader.assert_awaited_once()
        assert timer.call_args_list[1].args[0] == expected_budget
    api.async_switch_lock.assert_awaited_once()
    assert coordinator.command_diagnostics["elapsed_seconds"] == elapsed
    await coordinator.async_shutdown()


async def test_repeated_commands_never_lower_the_freshness_fence(hass, entry, row):
    api = AsyncMock()
    api.async_command_complete.side_effect = DeslocCommandTimeout("Expired")
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    with patch.object(coordinator, "async_refresh", new=AsyncMock()):
        with pytest.raises(HomeAssistantError):
            await coordinator.async_set_locked(False)
        coordinator.async_set_updated_data(Device.from_json(dict(row, doorStateUpdateTime=row["doorStateUpdateTime"] - 1000)))
        with pytest.raises(HomeAssistantError):
            await coordinator.async_set_locked(True)
    coordinator.async_set_updated_data(Device.from_json(row))
    assert coordinator.is_locked is None, "the first pre-command timestamp stays stale after a retry"
    coordinator.async_set_updated_data(Device.from_json(dict(row, doorStateUpdateTime=row["doorStateUpdateTime"] + 1)))
    assert coordinator.is_locked is True
    assert api.async_switch_lock.await_count == 2, "only the two explicit attempts were sent"
    await coordinator.async_shutdown()
