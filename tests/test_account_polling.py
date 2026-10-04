"""Synthetic concurrency and freshness tests; no DESLOC calls or credentials."""
import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.desloc.account import DeslocAccount
from custom_components.desloc.api import (
    DeslocAuthError, DeslocProtocolError, DeslocRateLimitError, Device,
)


def account_client():
    return Mock(async_devices=AsyncMock(), raise_if_blocked=Mock())


async def test_polls_share_one_complete_list_and_only_briefly_cache(row):
    api = account_client()
    started, release = asyncio.Event(), asyncio.Event()
    devices = [Device.from_json(row)]

    async def read():
        started.set()
        await release.wait()
        return devices

    api.async_devices.side_effect = read
    account = DeslocAccount(api)
    first = asyncio.create_task(account.async_devices())
    await started.wait()
    second = asyncio.create_task(account.async_devices())
    await asyncio.sleep(0)
    release.set()
    assert await first == await second == devices
    assert await account.async_devices() == devices
    api.async_devices.assert_awaited_once()
    account._completed_at -= 6
    assert await account.async_devices() == devices
    assert api.async_devices.await_count == 2
    await account.async_close()


async def test_confirmation_cannot_join_an_older_inflight_list(row):
    api = account_client()
    started, release = asyncio.Event(), asyncio.Event()
    old = Device.from_json(row)
    fresh = Device.from_json(dict(row, doorState=1, doorStateUpdateTime=old.door_state_updated_ms + 1000))
    calls = 0

    async def read():
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            await release.wait()
            return [old]
        return [fresh]

    api.async_devices.side_effect = read
    account = DeslocAccount(api)
    previous_poll = asyncio.create_task(account.async_devices())
    await started.wait()
    confirmation = asyncio.create_task(account.async_devices(force_refresh=True))
    await asyncio.sleep(0)
    release.set()
    assert await previous_poll == [old]
    assert await confirmation == [fresh]
    assert calls == 2
    await account.async_close()


async def test_confirmation_bypasses_a_completed_snapshot(row):
    api = account_client()
    old = Device.from_json(row)
    fresh = Device.from_json(dict(row, batteryValue=12))
    api.async_devices.side_effect = [[old], [fresh]]
    account = DeslocAccount(api)
    assert await account.async_devices() == [old]
    assert await account.async_devices(force_refresh=True) == [fresh]
    assert api.async_devices.await_count == 2
    await account.async_close()


async def test_cancelling_one_lock_waiter_keeps_other_lock_read_alive(row):
    api = account_client()
    started, release = asyncio.Event(), asyncio.Event()

    async def read():
        started.set()
        await release.wait()
        return [Device.from_json(row)]

    api.async_devices.side_effect = read
    account = DeslocAccount(api)
    first = asyncio.create_task(account.async_devices())
    await started.wait()
    second = asyncio.create_task(account.async_devices())
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert account._task is not None and not account._task.cancelled()
    release.set()
    assert await second == [Device.from_json(row)]
    api.async_devices.assert_awaited_once()
    await account.async_close()


async def test_failure_discards_previous_snapshot_and_allows_later_read(row):
    api = account_client()
    device = Device.from_json(row)
    api.async_devices.side_effect = [[device], DeslocProtocolError("Malformed second page"), []]
    account = DeslocAccount(api)
    assert await account.async_devices() == [device]
    with pytest.raises(DeslocProtocolError):
        await account.async_devices(force_refresh=True)
    assert account._task is None
    assert await account.async_devices() == []
    assert api.async_devices.await_count == 3
    await account.async_close()


@pytest.mark.parametrize("failure", [DeslocAuthError("Revoked"), DeslocRateLimitError("Backoff")])
async def test_blocked_session_never_returns_cached_success(row, failure):
    api = account_client()
    api.async_devices.return_value = [Device.from_json(row)]
    account = DeslocAccount(api)
    await account.async_devices()
    api.raise_if_blocked.side_effect = failure
    with pytest.raises(type(failure)):
        await account.async_devices()
    api.async_devices.assert_awaited_once()
    await account.async_close()


async def test_revocation_from_another_request_blocks_real_client_cache(transport):
    api, session, response, _ = transport
    account = DeslocAccount(api)
    await account.async_devices()
    response.status = 401
    with pytest.raises(DeslocAuthError):
        await api.async_command_complete("synthetic-command")
    with pytest.raises(DeslocAuthError):
        await account.async_devices()
    assert session.post.call_count == 2
    await account.async_close()


async def test_rate_limit_from_another_request_blocks_real_client_cache(transport):
    api, session, response, _ = transport
    account = DeslocAccount(api)
    await account.async_devices()
    response.status = 429
    with pytest.raises(DeslocRateLimitError):
        await api.async_command_complete("synthetic-command")
    with pytest.raises(DeslocRateLimitError):
        await account.async_devices()
    with pytest.raises(DeslocRateLimitError):
        await api.async_switch_lock(123, unlock=True)
    assert session.post.call_count == 2
    await account.async_close()


async def test_close_cancels_detached_read_without_leaving_task(row):
    api = account_client()
    started = asyncio.Event()

    async def read():
        started.set()
        await asyncio.Event().wait()

    api.async_devices.side_effect = read
    account = DeslocAccount(api)
    waiter = asyncio.create_task(account.async_devices())
    await started.wait()
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    await account.async_close()
    assert account._task is None
    assert account._snapshot is None


async def test_failed_detached_read_consumes_its_exception():
    api = account_client()
    started, release = asyncio.Event(), asyncio.Event()

    async def read():
        started.set()
        await release.wait()
        raise DeslocProtocolError("Synthetic failure")

    api.async_devices.side_effect = read
    account = DeslocAccount(api)
    waiter = asyncio.create_task(account.async_devices())
    await started.wait()
    task = account._task
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    release.set()
    # Await task completion without retrieving its exception ourselves; its
    # done callback must prevent an unhandled-exception warning after unload.
    await asyncio.wait([task])
    assert account._task is None
    assert not task._log_traceback
    await account.async_close()
