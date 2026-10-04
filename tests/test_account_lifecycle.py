"""Exercise shared account ownership through real HA entry lifecycle hooks."""
import asyncio
from dataclasses import asdict, replace
from pathlib import Path
from types import MappingProxyType
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.setup import async_setup_component

from custom_components.desloc.account import _STATE_KEY
from custom_components.desloc.api import DeslocConnectionError, Device


def saved_entry(device, credentials):
    """Build independent lock entries with synthetic saved session data."""
    return ConfigEntry(
        version=1, minor_version=1, domain="desloc", title=device.name,
        data={"mac": device.mac, "device_id": device.id,
              "credentials": asdict(credentials), "auth_type": "session"},
        source="user", unique_id=device.mac, options={},
        discovery_keys=MappingProxyType({}), subentries_data=[],
    )


@pytest.fixture
async def lifecycle_environment(hass, row):
    Path(hass.config.path("custom_components")).symlink_to(
        Path(__file__).resolve().parents[1] / "custom_components", target_is_directory=True)
    loader.async_setup(hass)
    assert await async_load_base_functionality(hass)
    assert await async_setup_component(hass, "desloc", {})
    devices = [Device.from_json(row), Device.from_json(dict(
        row, id=456, mac="00:11:22:33:44:66", deviceName="Second lock"))]
    read = AsyncMock(return_value=devices)
    forbidden = AsyncMock(side_effect=AssertionError("Lifecycle tests must never log in or write"))
    with patch("custom_components.desloc.async_get_clientsession", new=lambda hass: None), patch(
        "custom_components.desloc.api.DeslocClient.async_devices", new=read,
    ), patch("custom_components.desloc.api.DeslocClient._login", new=forbidden), patch(
        "custom_components.desloc.api.DeslocClient.async_switch_lock", new=forbidden,
    ), patch("custom_components.desloc.api.DeslocClient.async_create_access_user", new=forbidden), patch(
        "custom_components.desloc.api.DeslocClient.async_add_pin", new=forbidden,
    ):
        yield hass, devices, read
        forbidden.assert_not_awaited()


async def test_shared_account_survives_peer_unload_and_final_unload_cancels_fetch(
    lifecycle_environment, credentials,
):
    hass, devices, read = lifecycle_environment
    first, second = [saved_entry(device, credentials) for device in devices]
    await hass.config_entries.async_add(first)
    await hass.config_entries.async_add(second)
    assert first.state is second.state is ConfigEntryState.LOADED
    account = first.runtime_data.account
    assert second.runtime_data.account is account
    assert first.runtime_data.client is second.runtime_data.client is account.client
    assert account.references == 2
    assert len(hass.data[_STATE_KEY]) == 1
    read.assert_awaited_once()

    assert await hass.config_entries.async_unload(first.entry_id)
    assert second.state is ConfigEntryState.LOADED
    assert account.references == 1
    assert hass.data[_STATE_KEY][credentials] is account
    assert await second.runtime_data.account.async_devices(force_refresh=True) == devices
    assert read.await_count == 2

    started = asyncio.Event()

    async def blocked_read():
        started.set()
        await asyncio.Event().wait()

    read.side_effect = blocked_read
    waiter = asyncio.create_task(account.async_devices(force_refresh=True))
    try:
        async with asyncio.timeout(2):
            await started.wait()
            fetch = account._task
            assert fetch is not None and not fetch.done()
            assert await hass.config_entries.async_unload(second.entry_id)
            with pytest.raises(asyncio.CancelledError):
                await waiter
        assert fetch.cancelled()
        assert account.references == 0
        assert account._task is None
        assert account._snapshot is None
        assert _STATE_KEY not in hass.data
    finally:
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


@pytest.mark.parametrize("changed", [
    {"token": "another-synthetic-session"},
    {"app_device_id": "another-installation"},
    {"app_version": "9.9.9"},
    {"sys_type": "2"},
])
async def test_different_saved_session_or_headers_do_not_share_accounts(
    lifecycle_environment, credentials, changed,
):
    hass, devices, read = lifecycle_environment
    other_credentials = replace(credentials, **changed)
    first = saved_entry(devices[0], credentials)
    second = saved_entry(devices[1], other_credentials)
    await hass.config_entries.async_add(first)
    await hass.config_entries.async_add(second)
    first_account, second_account = first.runtime_data.account, second.runtime_data.account
    assert first.state is second.state is ConfigEntryState.LOADED
    assert first_account is not second_account
    assert first_account.client is not second_account.client
    assert first_account.client.session_credentials == credentials
    assert second_account.client.session_credentials == other_credentials
    assert first_account.references == second_account.references == 1
    assert set(hass.data[_STATE_KEY]) == {credentials, other_credentials}
    assert read.await_count == 2

    assert await hass.config_entries.async_unload(first.entry_id)
    assert first_account.references == 0
    assert set(hass.data[_STATE_KEY]) == {other_credentials}
    assert await second_account.async_devices(force_refresh=True) == devices
    assert await hass.config_entries.async_unload(second.entry_id)
    assert _STATE_KEY not in hass.data


async def test_failed_initial_refresh_releases_account_before_retry(
    lifecycle_environment, credentials,
):
    hass, devices, read = lifecycle_environment
    entry = saved_entry(devices[0], credentials)
    read.side_effect = DeslocConnectionError("Synthetic read failure")
    await hass.config_entries.async_add(entry)
    failed_account = entry.runtime_data.account
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert failed_account.references == 0
    assert failed_account._task is None
    assert failed_account._snapshot is None
    assert _STATE_KEY not in hass.data
    assert not hass.states.async_all("lock")

    read.side_effect = None
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.account is not failed_account
    assert entry.runtime_data.account.references == 1
    assert hass.data[_STATE_KEY][credentials] is entry.runtime_data.account
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert _STATE_KEY not in hass.data


async def test_reloading_replaced_credentials_retires_old_account_after_last_peer(
    lifecycle_environment, credentials,
):
    hass, devices, _ = lifecycle_environment
    first, second = [saved_entry(device, credentials) for device in devices]
    await hass.config_entries.async_add(first)
    await hass.config_entries.async_add(second)
    original_account = first.runtime_data.account
    replacement = replace(credentials, token="replacement-synthetic-session")

    # Reauthentication updates saved data and reloads peers independently.
    hass.config_entries.async_update_entry(first, data={
        **first.data, "credentials": asdict(replacement)})
    assert await hass.config_entries.async_reload(first.entry_id)
    replacement_account = first.runtime_data.account
    assert replacement_account is not original_account
    assert original_account.references == replacement_account.references == 1
    assert second.runtime_data.account is original_account
    assert second.runtime_data.client.session_credentials == credentials
    assert set(hass.data[_STATE_KEY]) == {credentials, replacement}

    hass.config_entries.async_update_entry(second, data={
        **second.data, "credentials": asdict(replacement)})
    assert await hass.config_entries.async_reload(second.entry_id)
    assert second.runtime_data.account is replacement_account
    assert replacement_account.references == 2
    assert replacement_account.client.session_credentials == replacement
    assert original_account.references == 0
    assert original_account._snapshot is None
    assert set(hass.data[_STATE_KEY]) == {replacement}
    assert await hass.config_entries.async_unload(first.entry_id)
    assert await hass.config_entries.async_unload(second.entry_id)
    assert _STATE_KEY not in hass.data


async def test_cancelled_setup_releases_account_and_cancels_unowned_fetch(
    lifecycle_environment, credentials,
):
    hass, devices, read = lifecycle_environment
    entry = saved_entry(devices[0], credentials)
    started = asyncio.Event()

    async def blocked_read():
        started.set()
        await asyncio.Event().wait()

    read.side_effect = blocked_read
    setup = asyncio.create_task(hass.config_entries.async_add(entry))
    try:
        async with asyncio.timeout(2):
            await started.wait()
            account = entry.runtime_data.account
            fetch = account._task
            assert account.references == 1
            assert fetch is not None and not fetch.done()
            setup.cancel()
            with pytest.raises(asyncio.CancelledError):
                await setup
        assert entry.state is ConfigEntryState.SETUP_ERROR
        assert account.references == 0
        assert fetch.cancelled()
        assert account._task is None
        assert account._snapshot is None
        assert _STATE_KEY not in hass.data
    finally:
        setup.cancel()
        await asyncio.gather(setup, return_exceptions=True)
