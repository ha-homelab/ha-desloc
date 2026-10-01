"""Share one cloud status request between the device entities."""
import logging
import asyncio
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DeslocAuthError, DeslocClient, DeslocError, Device
from .const import CONF_MAC, DOMAIN, POLL_SECONDS

LOGGER = logging.getLogger(__name__)


class DeslocCoordinator(DataUpdateCoordinator[Device | None]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: DeslocClient) -> None:
        super().__init__(hass, LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=POLL_SECONDS), always_update=False)
        self.client = client
        self.mac = entry.data[CONF_MAC]
        self.entry = entry
        self.pending_target: bool | None = None
        self._command_lock = asyncio.Lock()
        self._state_must_be_newer_than: int | None = None

    @property
    def is_locked(self) -> bool | None:
        device = self.data
        if device is None:
            return None
        if self._state_must_be_newer_than is not None and (
            device.door_state_updated_ms is None
            or device.door_state_updated_ms <= self._state_must_be_newer_than
        ):
            return None
        return device.is_locked

    async def async_set_locked(self, locked: bool) -> None:
        """Follow the app's command/result protocol without replaying actions."""
        if self._command_lock.locked():
            raise HomeAssistantError("A DESLOC command is already in progress")
        if not self.last_update_success or self.data is None:
            raise HomeAssistantError("DESLOC status is unavailable")
        async with self._command_lock:
            self._state_must_be_newer_than = self.data.door_state_updated_ms or 0
            self.pending_target = locked
            self.async_update_listeners()
            try:
                async with asyncio.timeout(45):
                    command_id = await self.client.async_switch_lock(self.data.id, unlock=not locked)
                    while not await self.client.async_command_complete(command_id):
                        await asyncio.sleep(2)
                    # The app's result can precede the cloud's state update.
                    for _ in range(6):
                        await self.async_refresh()
                        if self.is_locked is locked:
                            return
                        await asyncio.sleep(2)
                    raise HomeAssistantError("DESLOC acknowledged the command but the new lock state is not confirmed")
            except DeslocAuthError:
                self.entry.async_start_reauth(self.hass)
                raise HomeAssistantError("DESLOC session expired; renew the session") from None
            except DeslocError as err:
                raise HomeAssistantError(str(err)) from None
            except TimeoutError:
                raise HomeAssistantError("DESLOC command confirmation timed out; check the lock before retrying") from None
            finally:
                self.pending_target = None
                self.async_update_listeners()

    async def _async_update_data(self) -> Device | None:
        try:
            devices = await self.client.async_devices()
        except DeslocAuthError:
            raise ConfigEntryAuthFailed("DESLOC session expired; capture a new session") from None
        except DeslocError as err:
            raise UpdateFailed(str(err)) from None
        return next((device for device in devices if device.mac == self.mac), None)
