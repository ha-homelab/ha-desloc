"""No physical commands: command and cloud responses are synthetic."""
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
    with pytest.raises(HomeAssistantError):
        await coordinator.async_set_locked(False)
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
    ), pytest.raises(HomeAssistantError, match="not confirmed"):
        await coordinator.async_set_locked(True)
    api.async_switch_lock.assert_awaited_once()
    assert coordinator.is_locked is None
    await coordinator.async_shutdown()


async def test_busy_command_rejected(hass, entry, row):
    api = AsyncMock()
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(Device.from_json(row))
    async with coordinator._command_lock:
        with pytest.raises(HomeAssistantError, match="already in progress"):
            await coordinator.async_set_locked(False)
    api.async_switch_lock.assert_not_called()
    await coordinator.async_shutdown()

async def test_unavailable_status_blocks_command_without_api_call(hass, entry, row):
    """No lock mutation when coordinator has no confirmed device status."""
    api = AsyncMock()
    coordinator = DeslocCoordinator(hass, entry, api)
    assert coordinator.data is None
    with pytest.raises(HomeAssistantError, match="status is unavailable"):
        await coordinator.async_set_locked(True)
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
