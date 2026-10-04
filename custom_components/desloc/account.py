"""Share short-lived, complete device snapshots between one session's locks."""
import asyncio
from contextlib import suppress
import time

import aiohttp
from homeassistant.core import HomeAssistant

from .api import Credentials, DeslocClient, Device
from .const import DOMAIN

_STATE_KEY = f"{DOMAIN}_account_sessions"
DEVICE_CACHE_SECONDS = 5


class DeslocAccount:
    """One transport/auth state and one in-flight list walk per saved session.

    Ordinary polls share a snapshot for at most five seconds. A confirmation
    read must start after its caller asks for fresh data, even when a previous
    poll is still in flight. Writes are never cached, queued, or replayed here.
    """

    def __init__(self, client: DeslocClient) -> None:
        self.client = client
        self.references = 0
        self._task: asyncio.Task[list[Device]] | None = None
        self._started_at = 0.0
        self._snapshot: list[Device] | None = None
        self._completed_at = 0.0

    async def _fetch(self) -> list[Device]:
        try:
            devices = await self.client.async_devices()
            self.client.raise_if_blocked()
            self._snapshot = devices
            self._completed_at = time.monotonic()
            return devices
        except BaseException:
            # A failed page walk must not leave an older successful list usable.
            self._snapshot = None
            raise
        finally:
            self._task = None

    @staticmethod
    def _consume_result(task: asyncio.Task[list[Device]]) -> None:
        # A cancelled waiter does not own the shared task. Retrieve a later
        # failure even if every waiter has since unloaded or been cancelled.
        if not task.cancelled():
            task.exception()

    async def async_devices(self, *, force_refresh: bool = False) -> list[Device]:
        self.client.raise_if_blocked()
        requested_at = time.monotonic()
        if (not force_refresh and self._snapshot is not None
                and requested_at - self._completed_at < DEVICE_CACHE_SECONDS):
            return self._snapshot
        while True:
            if self._task is None:
                self._started_at = time.monotonic()
                self._task = asyncio.create_task(self._fetch())
                self._task.add_done_callback(self._consume_result)
            task, started_at = self._task, self._started_at
            devices = await asyncio.shield(task)
            self.client.raise_if_blocked()
            if not force_refresh or started_at >= requested_at:
                return devices
            # Do not use an in-flight request started before confirmation.

    async def async_close(self) -> None:
        self._snapshot = None
        if (task := self._task) is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


def get_account(
    hass: HomeAssistant, session: aiohttp.ClientSession, credentials: Credentials,
) -> DeslocAccount:
    """Acquire an account shared only by identical tokens AND request headers."""
    accounts: dict[Credentials, DeslocAccount] = hass.data.setdefault(_STATE_KEY, {})
    if (account := accounts.get(credentials)) is None:
        account = accounts[credentials] = DeslocAccount(DeslocClient(session, credentials))
    account.references += 1
    return account


async def async_release_account(
    hass: HomeAssistant, credentials: Credentials, account: DeslocAccount,
) -> None:
    account.references -= 1
    if account.references:
        return
    accounts = hass.data[_STATE_KEY]
    if accounts.get(credentials) is account:
        del accounts[credentials]
    if not accounts:
        del hass.data[_STATE_KEY]
    await account.async_close()
