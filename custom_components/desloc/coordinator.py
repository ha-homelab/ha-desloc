"""Share one cloud status request between the device entities."""
import logging
import asyncio
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .account import DeslocAccount
from .api import (DeslocAuthError, DeslocClient, DeslocClockError, DeslocCommandTimeout,
    DeslocConnectionError, DeslocError, DeslocExistingUserPinUnconfirmed,
    DeslocProtocolError, DeslocRateLimitError, DeslocUserExists, Device, validate_pin_user)
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
        self._command_started: float | None = None
        self._last_command: dict[str, Any] = self._new_command_diagnostics()

    @staticmethod
    def _new_command_diagnostics() -> dict[str, Any]:
        """Fixed categories only: never retain request IDs, bodies or direction."""
        return {
            "phase": "idle", "outcome": "not_started", "elapsed_seconds": 0.0,
            "result_poll_count": 0, "accepted": False, "acknowledged": False,
            "post_expiry_refresh": "not_attempted", "error_kind": None,
        }

    @property
    def awaiting_fresh_state(self) -> bool:
        """A command invalidated this report and no newer timestamp has arrived."""
        return self._state_must_be_newer_than is not None and (
            self.data is None or self.data.door_state_updated_ms is None
            or self.data.door_state_updated_ms <= self._state_must_be_newer_than
        )

    @property
    def command_diagnostics(self) -> dict[str, Any]:
        """Return a detached, allowlisted snapshot without activity timestamps."""
        snapshot = dict(self._last_command)
        if self._command_started is not None:
            snapshot["elapsed_seconds"] = round(max(0.0, time.monotonic() - self._command_started), 3)
        snapshot["awaiting_fresh_state"] = self.awaiting_fresh_state
        return snapshot

    def _command_phase(self, phase: str) -> None:
        self._last_command["phase"] = phase
        LOGGER.debug("DESLOC command phase=%s", phase)

    @property
    def is_locked(self) -> bool | None:
        device = self.data
        if device is None:
            return None
        if self.awaiting_fresh_state:
            return None
        return device.is_locked

    async def async_set_locked(self, locked: bool) -> None:
        """Follow the app's command/result protocol without replaying actions."""
        if self._command_lock.locked():
            raise DeslocCommandInProgress("A DESLOC command is already in progress",
                translation_domain=DOMAIN, translation_key="command_in_progress")
        if not self.last_update_success or self.data is None:
            raise DeslocUnavailable("DESLOC status is unavailable",
                translation_domain=DOMAIN, translation_key="unavailable")
        async with self._command_lock:
            self._state_must_be_newer_than = max(
                self._state_must_be_newer_than or 0, self.data.door_state_updated_ms or 0,
            )
            self._last_command = self._new_command_diagnostics()
            self._last_command["outcome"] = "pending"
            started = time.monotonic()
            self._command_started = started
            deadline = started + 45
            self.pending_target = locked
            self.async_update_listeners()
            try:
                async with asyncio.timeout(45):
                    self._command_phase("sending")
                    command_id = await self.client.async_switch_lock(self.data.id, unlock=not locked)
                    self._last_command["accepted"] = True
                    self._command_phase("waiting_result")
                    while True:
                        self._last_command["result_poll_count"] += 1
                        if await self.client.async_command_complete(command_id):
                            self._last_command["acknowledged"] = True
                            break
                        await asyncio.sleep(2)
                    # The app's result can precede the cloud's state update.
                    self._command_phase("confirming_state")
                    for _ in range(6):
                        await self.async_refresh()
                        if self.is_locked is locked:
                            self._last_command["outcome"] = "confirmed"
                            return
                        await asyncio.sleep(2)
                    self._last_command["outcome"] = "state_unconfirmed"
                    raise HomeAssistantError("DESLOC acknowledged the command but the new lock state is not confirmed",
                        translation_domain=DOMAIN, translation_key="command_unconfirmed")
            except DeslocAuthError:
                self._last_command["outcome"] = "auth_required"
                self.entry.async_start_reauth(self.hass)
                raise HomeAssistantError("DESLOC authentication requires attention; reauthenticate in Home Assistant",
                    translation_domain=DOMAIN, translation_key="auth_required") from None
            except DeslocCommandTimeout:
                self._last_command["outcome"] = "result_expired"
                # A lost result is not proof of either bolt state. Read once,
                # using only the original command's remaining budget; preserve
                # the expiry error even if this read fails or confirms a state.
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    LOGGER.debug("DESLOC command result expired; refreshing reported state once")
                    try:
                        async with asyncio.timeout(min(5.0, remaining)):
                            await self.async_refresh()
                        self._last_command["post_expiry_refresh"] = "success" if self.last_update_success else "failed"
                    except TimeoutError:
                        self._last_command["post_expiry_refresh"] = "timed_out"
                    except asyncio.CancelledError:
                        self._last_command["post_expiry_refresh"] = "cancelled"
                        raise
                    except Exception:
                        self._last_command["post_expiry_refresh"] = "failed"
                raise HomeAssistantError("DESLOC command result expired; check the lock before retrying",
                    translation_domain=DOMAIN, translation_key="command_timeout") from None
            except DeslocError as err:
                self._last_command["outcome"] = "failed"
                self._last_command["error_kind"] = next((kind for error_type, kind in (
                    (DeslocConnectionError, "connection_error"),
                    (DeslocRateLimitError, "rate_limited"),
                    (DeslocProtocolError, "protocol_error"),
                    (DeslocClockError, "clock_error"),
                ) if isinstance(err, error_type)), "unknown_api_error")
                raise HomeAssistantError(str(err), translation_domain=DOMAIN, translation_key="command_failed") from None
            except TimeoutError:
                self._last_command["outcome"] = "timed_out"
                raise HomeAssistantError("DESLOC command confirmation timed out; check the lock before retrying",
                    translation_domain=DOMAIN, translation_key="command_timeout") from None
            except asyncio.CancelledError:
                self._last_command["outcome"] = "cancelled"
                raise
            finally:
                if self._last_command["outcome"] == "pending":
                    self._last_command["outcome"] = "failed"
                self._last_command["elapsed_seconds"] = round(max(0.0, time.monotonic() - started), 3)
                self._command_started = None
                self.pending_target = None
                snapshot = self.command_diagnostics
                log = LOGGER.debug if snapshot["outcome"] in {"confirmed", "cancelled"} else LOGGER.warning
                log("DESLOC command outcome=%s error_kind=%s phase=%s elapsed_seconds=%s result_poll_count=%s accepted=%s acknowledged=%s awaiting_fresh_state=%s post_expiry_refresh=%s",
                    snapshot["outcome"], snapshot["error_kind"], snapshot["phase"], snapshot["elapsed_seconds"],
                    snapshot["result_poll_count"], snapshot["accepted"], snapshot["acknowledged"],
                    snapshot["awaiting_fresh_state"], snapshot["post_expiry_refresh"])
                self.async_update_listeners()

    async def _async_update_data(self) -> Device | None:
        try:
            if self.account is None:
                devices = await self.client.async_devices()
            else:
                devices = await self.account.async_devices(force_refresh=self.pending_target is not None)
        except DeslocAuthError:
            raise ConfigEntryAuthFailed("DESLOC authentication requires attention; reauthenticate in Home Assistant",
                translation_domain=DOMAIN, translation_key="auth_required") from None
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
            raise DeslocCommandInProgress("A DESLOC command is already in progress",
                translation_domain=DOMAIN, translation_key="command_in_progress")
        if not self.last_update_success or self.data is None:
            raise DeslocUnavailable("DESLOC status is unavailable",
                translation_domain=DOMAIN, translation_key="unavailable")
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
                    raise HomeAssistantError("PIN installation is unconfirmed; check the DESLOC app",
                        translation_domain=DOMAIN, translation_key="pin_creation_uncertain")
            except DeslocUserExists:
                raise
            except DeslocAuthError:
                self.entry.async_start_reauth(self.hass)
                if not write_attempted:
                    raise DeslocPinPreflightFailed("Authentication failed before any changes were attempted",
                        translation_domain=DOMAIN, translation_key="pin_preflight_failed") from None
                raise HomeAssistantError("Authentication failed; check the DESLOC app before retrying",
                    translation_domain=DOMAIN, translation_key="pin_creation_uncertain") from None
            except (DeslocError, TimeoutError):
                if not write_attempted:
                    raise DeslocPinPreflightFailed("Could not check existing users; no changes were attempted",
                        translation_domain=DOMAIN, translation_key="pin_preflight_failed") from None
                # Creation may have succeeded before PIN installation failed.
                # Neither retry nor delete a possibly created user automatically.
                raise HomeAssistantError("PIN creation is uncertain; check the DESLOC app before retrying",
                    translation_domain=DOMAIN, translation_key="pin_creation_uncertain") from None
