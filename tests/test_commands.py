"""No physical commands: command and cloud responses are synthetic."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from custom_components.desloc.account import DeslocAccount
from custom_components.desloc.api import (
    Device, DeslocAuthError, DeslocConnectionError, DeslocCommandTimeout, DeslocRateLimitError,
)
from custom_components.desloc.coordinator import DeslocCoordinator
from custom_components.desloc.lock import DeslocLock

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


@pytest.mark.parametrize("failure", [DeslocConnectionError("Connection lost")])
async def test_failure_leaves_old_state_unknown_without_retry(hass, entry, row, failure):
    api = AsyncMock()
    api.async_switch_lock.side_effect = failure
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    with patch.object(coordinator, "async_refresh", new=AsyncMock()), pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    assert error.value.translation_domain == "desloc"
    assert error.value.translation_key == "command_failed"
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


@pytest.fixture
def command_clock(monkeypatch):
    """Advance only the command's monotonic clock; keep real asyncio cancellation."""
    clock = SimpleNamespace(value=100.0, sleeps=[])
    clock.monotonic = lambda: clock.value
    real_sleep = asyncio.sleep

    async def sleep(seconds):
        assert 0 < seconds <= 2, "confirmation retries must remain bounded and paced"
        clock.sleeps.append(seconds)
        clock.value += seconds
        await real_sleep(0)

    monkeypatch.setattr("custom_components.desloc.coordinator.time", clock)
    monkeypatch.setattr("custom_components.desloc.coordinator.asyncio.sleep", sleep)
    return clock


async def test_vendor_expiry_then_late_state_confirmation_without_replaying_command(
    hass, entry, row, transport, command_clock,
):
    """Real 2206/2104 decoding switches to paced state reads, never a new write."""
    dr.async_setup(hass)
    await dr.async_load(hass)
    api, session, response, _ = transport
    response.json.side_effect = [
        {"status": 200, "success": True, "data": {"commandId": "private-command-id"}},
        {"status": 2206, "success": False},
        {"status": 2104, "success": False, "msg": "private-server-body"},
        {"status": 200, "success": True, "data": [row]},
        {"status": 200, "success": True, "data": [dict(row, doorState=2,
            doorStateUpdateTime=row["doorStateUpdateTime"] + 1000)]},
        {"status": 200, "success": True, "data": [dict(row, doorState=1,
            doorStateUpdateTime=row["doorStateUpdateTime"] + 2000)]},
    ]
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    await coordinator.async_set_locked(False)
    paths = [call.args[0] for call in session.post.call_args_list]
    assert sum(path.endswith("/remoteSwitchLock") for path in paths) == 1
    assert sum("/fecommand/result/" in path for path in paths) == 2
    assert sum(path.endswith("/api/device/list") for path in paths) == 3
    assert command_clock.sleeps == [2, 2, 2]
    assert coordinator.is_locked is False
    assert coordinator.pending_target is None
    assert not coordinator._command_lock.locked()
    snapshot = coordinator.command_diagnostics
    assert snapshot["outcome"] == "state_confirmed_after_expiry"
    assert snapshot["phase"] == "reconciling_state"
    assert snapshot["accepted"] is True
    assert snapshot["acknowledged"] is False, "fresh state must never fabricate a command acknowledgement"
    assert snapshot["result_expired"] is True
    assert snapshot["state_confirmed"] is True
    assert snapshot["result_poll_count"] == 2
    assert snapshot["state_poll_count"] == 3
    assert snapshot["awaiting_fresh_state"] is False
    assert snapshot["post_expiry_refresh"] == "success"
    assert snapshot["elapsed_seconds"] == 6
    await coordinator.async_shutdown()


@pytest.mark.parametrize("offset,reported_state,expected_state", [
    (None, 1, None), (-1000, 1, None), (0, 1, None), (1000, 2, True),
])
async def test_expiry_requires_fresh_matching_state_before_original_deadline(
    hass, entry, row, command_clock, offset, reported_state, expected_state,
):
    api = AsyncMock()
    api.async_switch_lock.return_value = "private-command-id"

    async def expire(_command_id):
        command_clock.value += 11
        raise DeslocCommandTimeout("private-response")

    api.async_command_complete.side_effect = expire
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    timestamp = None if offset is None else row["doorStateUpdateTime"] + offset
    read_times = []

    async def refresh():
        assert coordinator.pending_target is False
        assert coordinator._command_lock.locked()
        read_times.append(command_clock.value)
        coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=reported_state,
            doorStateUpdateTime=timestamp)))

    with patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=refresh)), \
            pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    assert error.value.translation_key == "command_timeout"
    assert "private-" not in str(error.value)
    assert read_times[0] == 111, "expiry must immediately start fresh-state reconciliation"
    assert len(read_times) > 6, "do not end the observation window after the old six-read cap"
    assert all(right - left == 2 for left, right in zip(read_times, read_times[1:]))
    assert max(read_times) < 145
    assert command_clock.value == 145, "expiry must not reset or extend the original 45-second budget"
    api.async_switch_lock.assert_awaited_once_with(123, unlock=True)
    api.async_command_complete.assert_awaited_once_with("private-command-id")
    assert coordinator.is_locked is expected_state
    snapshot = coordinator.command_diagnostics
    assert snapshot["outcome"] == "result_expired"
    assert snapshot["state_confirmed"] is False
    assert snapshot["result_expired"] is True
    assert snapshot["acknowledged"] is False
    assert snapshot["state_poll_count"] == len(read_times)
    assert snapshot["awaiting_fresh_state"] is (expected_state is None)
    assert coordinator.pending_target is None
    await coordinator.async_shutdown()


async def test_expiry_confirmation_bypasses_shared_account_snapshot(hass, entry, row, command_clock):
    """The five-second account cache must not hide a late report from reconciliation."""
    dr.async_setup(hass)
    await dr.async_load(hass)
    original = Device.from_json(row)
    fresh = Device.from_json(dict(row, doorState=1, doorStateUpdateTime=row["doorStateUpdateTime"] + 1))
    api = Mock(
        raise_if_blocked=Mock(),
        async_devices=AsyncMock(side_effect=[[original], [original], [fresh]]),
        async_switch_lock=AsyncMock(return_value="synthetic-command"),
        async_command_complete=AsyncMock(side_effect=DeslocCommandTimeout("Expired")),
    )
    account = DeslocAccount(api)
    coordinator = DeslocCoordinator(hass, entry, api, account=account)
    coordinator.async_set_updated_data((await account.async_devices())[0])
    await coordinator.async_set_locked(False)
    assert coordinator.is_locked is False
    assert api.async_devices.await_count == 3
    assert coordinator.command_diagnostics["state_poll_count"] == 2
    assert command_clock.sleeps == [2]
    api.async_switch_lock.assert_awaited_once_with(123, unlock=True)
    api.async_command_complete.assert_awaited_once()
    await coordinator.async_shutdown()
    await account.async_close()


async def test_failed_refresh_cannot_confirm_retained_fresh_matching_data(hass, entry, row, command_clock):
    """HA can retain data across a failed refresh; only a successful read can confirm."""
    api = AsyncMock()
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))

    async def expire(_command_id):
        # A separately delivered fresh report must not mask failure of every
        # post-expiry read made by this command's confirmation loop.
        coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=1,
            doorStateUpdateTime=row["doorStateUpdateTime"] + 1)))
        raise DeslocCommandTimeout("Expired")

    api.async_command_complete.side_effect = expire
    api.async_devices.side_effect = DeslocConnectionError("synthetic connection failure")
    with pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    assert error.value.translation_key == "command_timeout"
    assert api.async_devices.await_count > 1
    assert command_clock.value == 145
    assert coordinator.command_diagnostics["outcome"] == "result_expired"
    assert coordinator.command_diagnostics["state_confirmed"] is False
    assert coordinator.command_diagnostics["result_expired"] is True
    assert coordinator.command_diagnostics["post_expiry_refresh"] == "failed"
    api.async_switch_lock.assert_awaited_once()
    api.async_command_complete.assert_awaited_once()
    await coordinator.async_shutdown()


async def test_transient_read_failure_can_recover_without_another_command(hass, entry, row, command_clock):
    dr.async_setup(hass)
    await dr.async_load(hass)
    api = AsyncMock()
    api.async_command_complete.side_effect = DeslocCommandTimeout("Expired")
    api.async_devices.side_effect = [DeslocConnectionError("synthetic connection failure"), [
        Device.from_json(dict(row, doorState=1, doorStateUpdateTime=row["doorStateUpdateTime"] + 1)),
    ]]
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    await coordinator.async_set_locked(False)
    assert coordinator.command_diagnostics["outcome"] == "state_confirmed_after_expiry"
    assert coordinator.command_diagnostics["state_confirmed"] is True
    assert coordinator.command_diagnostics["acknowledged"] is False
    assert api.async_devices.await_count == 2
    assert command_clock.sleeps == [2]
    api.async_switch_lock.assert_awaited_once()
    api.async_command_complete.assert_awaited_once()
    await coordinator.async_shutdown()


@pytest.mark.parametrize("failure,translation,outcome,error_kind", [
    (DeslocAuthError("synthetic revoked token"), "auth_required", "auth_required", "auth_required"),
    (DeslocRateLimitError("synthetic rate limit"), "command_timeout", "result_expired", "rate_limited"),
])
async def test_expiry_reconciliation_stops_on_auth_or_rate_limit(
    hass, entry, row, command_clock, failure, translation, outcome, error_kind,
):
    """Exercise HA's real swallowed-refresh-error path, not just direct exceptions."""
    api = AsyncMock()
    api.async_command_complete.side_effect = DeslocCommandTimeout("Expired")
    api.async_devices.side_effect = failure
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    with patch.object(ConfigEntry, "async_start_reauth") as reauth, pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    assert error.value.translation_key == translation
    snapshot = coordinator.command_diagnostics
    assert snapshot["outcome"] == outcome
    assert snapshot["result_expired"] is True
    assert snapshot["state_confirmed"] is False
    assert snapshot["acknowledged"] is False
    assert snapshot["error_kind"] == error_kind
    assert snapshot["post_expiry_refresh"] == "failed"
    api.async_devices.assert_awaited_once()
    api.async_switch_lock.assert_awaited_once()
    api.async_command_complete.assert_awaited_once()
    if isinstance(failure, DeslocAuthError):
        assert reauth.called
    else:
        reauth.assert_not_called()
    assert not command_clock.sleeps
    assert coordinator.pending_target is None
    assert not coordinator._command_lock.locked()
    await coordinator.async_shutdown()


async def test_inflight_state_read_is_cancelled_at_original_deadline(hass, entry, row):
    api = AsyncMock()
    api.async_command_complete.side_effect = DeslocCommandTimeout("Expired")
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    cancelled = asyncio.Event()
    actual_timeout = asyncio.timeout
    budgets = []

    async def slow_refresh():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    def timeout(seconds):
        budgets.append(seconds)
        return actual_timeout(0.02 if len(budgets) == 1 else seconds)

    with patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=slow_refresh)) as reader, \
            patch("custom_components.desloc.coordinator.asyncio.timeout", side_effect=timeout), \
            pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    assert budgets[0] == 45
    assert cancelled.is_set()
    reader.assert_awaited_once()
    api.async_switch_lock.assert_awaited_once()
    api.async_command_complete.assert_awaited_once()
    assert error.value.translation_key == "command_timeout"
    assert coordinator.command_diagnostics["outcome"] == "result_expired"
    assert coordinator.command_diagnostics["result_expired"] is True
    assert coordinator.command_diagnostics["post_expiry_refresh"] == "timed_out"
    assert coordinator.pending_target is None
    assert not coordinator._command_lock.locked()
    await coordinator.async_shutdown()


async def test_cancellation_during_expiry_read_preserves_evidence_and_serialization(hass, entry, row):
    """A pending reconciliation owns the lock until cancellation has unwound."""
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
            with pytest.raises(HomeAssistantError) as busy:
                await coordinator.async_set_locked(True)
            assert busy.value.translation_key == "command_in_progress"
            with pytest.raises(HomeAssistantError) as pin_busy:
                await coordinator.async_add_pin_user("Synthetic guest", "123456")
            assert pin_busy.value.translation_key == "command_in_progress"
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
    api.async_access_users.assert_not_awaited()
    api.async_create_access_user.assert_not_awaited()
    assert coordinator.command_diagnostics["outcome"] == "cancelled"
    assert coordinator.command_diagnostics["result_expired"] is True
    assert coordinator.command_diagnostics["state_confirmed"] is False
    assert coordinator.command_diagnostics["post_expiry_refresh"] == "cancelled"
    assert coordinator.pending_target is None
    assert not coordinator._command_lock.locked()
    assert coordinator.is_locked is None
    await coordinator.async_shutdown()


@pytest.mark.parametrize("elapsed", [44.75, 45, 46])
async def test_expiry_observation_never_restarts_original_deadline(hass, entry, row, command_clock, elapsed):
    api = AsyncMock()

    async def expire(_command_id):
        command_clock.value += elapsed
        raise DeslocCommandTimeout("Expired")

    api.async_command_complete.side_effect = expire
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    actual_timeout = asyncio.timeout
    with patch("custom_components.desloc.coordinator.asyncio.timeout", wraps=actual_timeout) as timer, \
            patch.object(coordinator, "async_refresh", new=AsyncMock()) as reader, \
            pytest.raises(HomeAssistantError) as error:
        await coordinator.async_set_locked(False)
    assert error.value.translation_key == "command_timeout"
    if elapsed >= 45:
        reader.assert_not_awaited()
        assert not command_clock.sleeps
        assert coordinator.command_diagnostics["post_expiry_refresh"] == "not_attempted"
    else:
        reader.assert_awaited_once()
        assert sum(command_clock.sleeps) <= 0.25
        assert coordinator.command_diagnostics["elapsed_seconds"] <= 45
    assert timer.call_args_list[0].args[0] == 45
    api.async_switch_lock.assert_awaited_once()
    api.async_command_complete.assert_awaited_once()
    assert coordinator.command_diagnostics["result_expired"] is True
    assert coordinator.command_diagnostics["state_confirmed"] is False
    await coordinator.async_shutdown()


async def test_repeated_commands_never_lower_the_freshness_fence(hass, entry, row, command_clock):
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


@pytest.mark.parametrize("regressed_offset", [1000, 2000])
async def test_late_matching_report_must_advance_past_newer_opposite_report(
    hass, entry, row, command_clock, regressed_offset,
):
    api = AsyncMock()
    api.async_command_complete.side_effect = DeslocCommandTimeout("Expired")
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    reports = iter([(2, 2000), (1, regressed_offset), (1, 3000)])

    async def refresh():
        state, offset = next(reports)
        coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=state,
            doorStateUpdateTime=row["doorStateUpdateTime"] + offset)))

    with patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=refresh)) as reader:
        await coordinator.async_set_locked(False)
    assert reader.await_count == 3, "a matching but regressed/unchanged report is not confirmation"
    assert coordinator.command_diagnostics["state_confirmed"] is True
    assert coordinator.command_diagnostics["acknowledged"] is False
    assert command_clock.sleeps == [2, 2]
    api.async_switch_lock.assert_awaited_once()
    api.async_command_complete.assert_awaited_once()
    await coordinator.async_shutdown()


@pytest.mark.parametrize("report_elapsed,confirmed", [(44.99, True), (45.01, False)])
async def test_confirmation_must_finish_within_original_deadline(
    hass, entry, row, command_clock, report_elapsed, confirmed,
):
    api = AsyncMock()
    api.async_command_complete.side_effect = DeslocCommandTimeout("Expired")
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))

    async def refresh():
        command_clock.value = 100 + report_elapsed
        coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=1,
            doorStateUpdateTime=row["doorStateUpdateTime"] + 1)))

    with patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=refresh)):
        if confirmed:
            await coordinator.async_set_locked(False)
        else:
            with pytest.raises(HomeAssistantError) as error:
                await coordinator.async_set_locked(False)
            assert error.value.translation_key == "command_timeout"
    assert coordinator.command_diagnostics["state_confirmed"] is confirmed
    assert coordinator.command_diagnostics["acknowledged"] is False
    assert coordinator.command_diagnostics["result_expired"] is True
    api.async_switch_lock.assert_awaited_once()
    api.async_command_complete.assert_awaited_once()
    await coordinator.async_shutdown()


@pytest.mark.parametrize("rejected_offset", [1000, 2000, None], ids=["regressed", "contradictory-same-time", "missing-time"])
async def test_rejected_late_report_cannot_escape_through_entity_or_next_command(
    hass, entry, row, command_clock, rejected_offset,
):
    """A rejected target report must not become a confident Unlocked entity."""
    api = AsyncMock()
    api.async_command_complete.side_effect = DeslocCommandTimeout("Expired")
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    entity = DeslocLock(coordinator, "lock")
    latest_timestamp = row["doorStateUpdateTime"] + 2000
    rejected_timestamp = None if rejected_offset is None else row["doorStateUpdateTime"] + rejected_offset
    reads = 0

    async def first_attempt_refresh():
        nonlocal reads
        reads += 1
        if reads == 1:
            coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=2,
                doorStateUpdateTime=latest_timestamp)))
        else:
            coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=1,
                doorStateUpdateTime=rejected_timestamp)))

    with patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=first_attempt_refresh)), \
            pytest.raises(HomeAssistantError) as first_error:
        await coordinator.async_set_locked(False)
    assert first_error.value.translation_key == "command_timeout"
    assert reads > 1
    assert entity.is_locked is None, "the entity must reject the same stale target as command confirmation"
    assert not entity.is_unlocking
    assert coordinator.command_diagnostics["awaiting_fresh_state"] is True
    assert coordinator.command_diagnostics["state_confirmed"] is False
    assert coordinator.command_diagnostics["outcome"] == "result_expired"

    # A cached background poll cannot erase the T+2000 high-water mark.
    coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=1,
        doorStateUpdateTime=row["doorStateUpdateTime"] + 500)))
    assert entity.is_locked is None

    async def next_attempt_refresh():
        # This is newer than the currently cached data, yet older than the
        # trustworthy opposite report observed during the previous attempt.
        coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=1,
            doorStateUpdateTime=row["doorStateUpdateTime"] + 1500)))

    with patch.object(coordinator, "async_refresh", new=AsyncMock(side_effect=next_attempt_refresh)), \
            pytest.raises(HomeAssistantError) as next_error:
        await coordinator.async_set_locked(False)
    assert next_error.value.translation_key == "command_timeout"
    assert entity.is_locked is None
    assert coordinator.command_diagnostics["awaiting_fresh_state"] is True
    assert coordinator.command_diagnostics["state_confirmed"] is False
    assert api.async_switch_lock.await_count == 2, "only the two explicit user attempts may send a command"
    assert api.async_command_complete.await_count == 2, "each expired result is read only once"
    assert not coordinator._command_lock.locked()

    # Recovery still works when a genuinely newer report finally arrives.
    coordinator.async_set_updated_data(Device.from_json(dict(row, doorState=1,
        doorStateUpdateTime=latest_timestamp + 1)))
    assert entity.is_locked is False
    assert coordinator.command_diagnostics["awaiting_fresh_state"] is False
    assert coordinator.command_diagnostics["outcome"] == "result_expired", "later telemetry cannot rewrite the attempt's result"
    await coordinator.async_shutdown()
