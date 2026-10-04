"""Share one cloud status request between the device entities."""
import logging
import asyncio
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .account import DeslocAccount
from .api import (DeslocAuthError, DeslocClient, DeslocError,
    DeslocExistingUserPinUnconfirmed, DeslocUserExists, Device, validate_pin_user)
from .const import CONF_MAC, DOMAIN, POLL_SECONDS

LOGGER = logging.getLogger(__name__)


class DeslocCommandInProgress(HomeAssistantError):
    """Another operation owns this lock; no request was sent."""


class DeslocUnavailable(HomeAssistantError):
    """No usable device status exists; no request was sent."""


class DeslocPinPreflightFailed(HomeAssistantError):
    """A read failed before any user or PIN write was attempted."""


class DeslocCoordinator(DataUpdateCoordinator[Device | None]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: DeslocClient,
                 *, account: DeslocAccount | None = None) -> None:
        super().__init__(hass, LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=POLL_SECONDS), always_update=False)
        self.client = client
        self.account = account
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
            raise DeslocCommandInProgress("A DESLOC command is already in progress")
        if not self.last_update_success or self.data is None:
            raise DeslocUnavailable("DESLOC status is unavailable")
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
                raise HomeAssistantError("DESLOC authentication requires attention; reauthenticate in Home Assistant") from None
            except DeslocError as err:
                raise HomeAssistantError(str(err)) from None
            except TimeoutError:
                raise HomeAssistantError("DESLOC command confirmation timed out; check the lock before retrying") from None
            finally:
                self.pending_target = None
                self.async_update_listeners()

    async def _async_update_data(self) -> Device | None:
        try:
            if self.account is None:
                devices = await self.client.async_devices()
            else:
                devices = await self.account.async_devices(force_refresh=self.pending_target is not None)
        except DeslocAuthError:
            raise ConfigEntryAuthFailed("DESLOC authentication requires attention; reauthenticate in Home Assistant") from None
        except DeslocError as err:
            raise UpdateFailed(str(err)) from None
        device = next((device for device in devices if device.mac == self.mac), None)
        if device is not None:
            registry = dr.async_get(self.hass)
            if registered := registry.async_get_device_by_identifier((DOMAIN, self.mac), self.entry.entry_id):
                updates = {key: value for key, value in {
                    "name": device.name, "model": device.model, "sw_version": device.firmware,
                }.items() if getattr(registered, key) != value}
                if updates:
                    # User overrides (name_by_user), identifiers, and entity IDs
                    # are deliberately absent from these cloud metadata updates.
                    registry.async_update_device(registered.id, **updates)
        return device

    async def async_add_pin_user(self, name: str, pin: str) -> None:
        """Create a permanent user and PIN once, then verify device acknowledgement."""
        validate_pin_user(name, pin)
        name = name.strip()
        if self._command_lock.locked():
            raise DeslocCommandInProgress("A DESLOC command is already in progress")
        if not self.last_update_success or self.data is None:
            raise DeslocUnavailable("DESLOC status is unavailable")
        async with self._command_lock:
            write_attempted = False
            try:
                async with asyncio.timeout(60):
                    device_id = self.data.id
                    users = await self.client.async_access_users(device_id)
                    for user in users:
                        if user["accessName"].strip().casefold() == name.casefold():
                            if not await self.client.async_pin_present(
                                user["id"], device_id, user["accessName"],
                            ):
                                raise DeslocExistingUserPinUnconfirmed(
                                    "The user exists but its PIN record is unconfirmed; check the DESLOC app")
                            raise DeslocUserExists("A user with this name already exists")
                    write_attempted = True
                    access_id = await self.client.async_create_access_user(device_id, name)
                    command_id = await self.client.async_add_pin(access_id, name, pin)
                    while not await self.client.async_command_complete(command_id):
                        await asyncio.sleep(2)
                    for _ in range(6):
                        if await self.client.async_pin_present(access_id, device_id, name):
                            return
                        await asyncio.sleep(2)
                    raise HomeAssistantError("PIN installation is unconfirmed; check the DESLOC app")
            except DeslocUserExists:
                raise
            except DeslocAuthError:
                self.entry.async_start_reauth(self.hass)
                if not write_attempted:
                    raise DeslocPinPreflightFailed("Authentication failed before any changes were attempted") from None
                raise HomeAssistantError("Authentication failed; check the DESLOC app before retrying") from None
            except (DeslocError, TimeoutError):
                if not write_attempted:
                    raise DeslocPinPreflightFailed("Could not check existing users; no changes were attempted") from None
                # Creation may have succeeded before PIN installation failed.
                # Neither retry nor delete a possibly created user automatically.
                raise HomeAssistantError("PIN creation is uncertain; check the DESLOC app before retrying") from None
