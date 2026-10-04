"""DESLOC account login, email verification, and captured-session fallback."""
from dataclasses import asdict
from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import (AccountCredentials, Credentials, DeslocAuthError, DeslocCaptchaRequired,
    DeslocClient, DeslocClockError, DeslocError, DeslocInvalidCode, DeslocVerificationRequired,
    DeslocExistingUserPinUnconfirmed, DeslocUserExists, validate_pin_user)
from .const import CONF_CREDENTIALS, CONF_DEVICE_ID, CONF_MAC, DOMAIN
from .discovery import ValidatedDevice, async_reconcile_devices, is_valid_handoff
from .coordinator import DeslocCommandInProgress, DeslocPinPreflightFailed, DeslocUnavailable

PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
ACCOUNT_SCHEMA = vol.Schema({vol.Required("username"): str, vol.Required("password"): PASSWORD})
CODE_SCHEMA = vol.Schema({vol.Required("code"): PASSWORD})
SESSION_SCHEMA = vol.Schema({
    vol.Required("token"): PASSWORD,
    vol.Required("app_device_id"): str,
    vol.Optional("app_version", default="1.2.1"): str,
    vol.Optional("sys_type", default="1"): str,
})


class DeslocConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return DeslocOptionsFlow()

    def __init__(self) -> None:
        self._credentials: Credentials | AccountCredentials | None = None
        self._client: DeslocClient | None = None
        self._app_device_id = str(uuid4()).upper()

    def _target_entry(self):
        if self.source == "reauth":
            return self._get_reauth_entry()
        if self.source == "reconfigure":
            return self._get_reconfigure_entry()
        return None

    async def _validated(self) -> ConfigFlowResult:
        assert self._client is not None and self._credentials is not None
        devices = await self._client.async_devices()
        entry = self._target_entry()
        auth_type = "account" if isinstance(self._credentials, AccountCredentials) else "session"
        if entry is not None:
            device = next((d for d in devices if d.mac == entry.data[CONF_MAC]), None)
            if device is None:
                return self.async_abort(reason="device_mismatch")
        if not devices:
            return self.async_abort(reason="no_devices")
        created = await async_reconcile_devices(
            self.hass, devices, self._client.session_credentials, auth_type,
            target=entry)
        if entry is not None:
            return self.async_update_reload_and_abort(entry, data_updates={
                CONF_CREDENTIALS: asdict(self._client.session_credentials), CONF_DEVICE_ID: device.id,
                "auth_type": auth_type,
            })
        return self.async_abort(reason="devices_added" if created else "devices_updated")

    async def async_step_system(self, user_input: Any = None) -> ConfigFlowResult:
        """Create one lock from an authenticated, in-process account handoff."""
        if not is_valid_handoff(self.hass, user_input):
            return self.async_abort(reason="invalid_discovery")
        assert isinstance(user_input, ValidatedDevice)
        await self.async_set_unique_id(user_input.device.mac)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=user_input.device.name, data=user_input.entry_data())

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["account", "session"])

    async def async_step_account(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors = {}
        entry = self._target_entry()
        if entry is not None and entry.data.get("auth_type") == "account":
            self._app_device_id = entry.data[CONF_CREDENTIALS]["app_device_id"]
        if user_input is not None:
            try:
                self._credentials = AccountCredentials.from_password(
                    user_input["username"], user_input["password"], self._app_device_id)
                self._client = DeslocClient(async_get_clientsession(self.hass), self._credentials)
                return await self._validated()
            except DeslocVerificationRequired:
                try:
                    await self._client.async_send_verification_code()
                except DeslocError:
                    errors["base"] = "cannot_send_code"
                else:
                    return await self.async_step_verification()
            except DeslocCaptchaRequired:
                errors["base"] = "captcha_required"
            except DeslocClockError:
                errors["base"] = "clock_error"
            except DeslocAuthError:
                errors["base"] = "invalid_auth"
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_account"
            except DeslocError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="account", data_schema=ACCOUNT_SCHEMA, errors=errors)

    async def async_step_verification(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._client is None:
            return self.async_abort(reason="reauth_required")
        errors = {}
        if user_input is not None:
            try:
                await self._client.async_login(user_input["code"])
                return await self._validated()
            except (DeslocInvalidCode, DeslocVerificationRequired, ValueError, KeyError):
                errors["base"] = "invalid_code"
            except DeslocAuthError:
                errors["base"] = "invalid_auth"
            except DeslocError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="verification", data_schema=CODE_SCHEMA, errors=errors)

    async def _session_step(self, step_id: str, user_input: dict[str, Any] | None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            try:
                self._credentials = Credentials(**user_input)
                self._client = DeslocClient(async_get_clientsession(self.hass), self._credentials)
                return await self._validated()
            except (ValueError, TypeError):
                errors["base"] = "invalid_session"
            except DeslocAuthError:
                errors["base"] = "invalid_auth"
            except DeslocError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id=step_id, data_schema=SESSION_SCHEMA, errors=errors)

    async def async_step_session(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._session_step("session", user_input)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        if entry_data.get("auth_type") == "account":
            return await self.async_step_account()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._session_step("reauth_confirm", user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self.async_step_user()


class DeslocOptionsFlow(OptionsFlow):
    """Admin-only HA settings flow; PINs never enter options, entities, or services."""

    def __init__(self) -> None:
        self._submitted = False

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._submitted:
            return self.async_abort(reason="already_submitted")
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is None or not coordinator.last_update_success or coordinator.data is None:
            return self.async_abort(reason="unavailable")
        errors = {}
        if user_input is not None:
            try:
                validate_pin_user(user_input["name"], user_input["pin"])
                if user_input["pin"] != user_input.get("pin_confirm"):
                    errors["base"] = "pin_mismatch"
            except (ValueError, KeyError, TypeError):
                errors["base"] = "invalid_pin_user"
            if not errors:
                self._submitted = True
                try:
                    await coordinator.async_add_pin_user(user_input["name"], user_input["pin"])
                except DeslocExistingUserPinUnconfirmed:
                    return self.async_abort(reason="existing_user_pin_unconfirmed")
                except DeslocUserExists:
                    return self.async_abort(reason="user_exists")
                except DeslocCommandInProgress:
                    return self.async_abort(reason="command_in_progress")
                except DeslocUnavailable:
                    return self.async_abort(reason="unavailable")
                except DeslocPinPreflightFailed:
                    return self.async_abort(reason="pin_preflight_failed")
                except HomeAssistantError:
                    return self.async_abort(reason="pin_creation_uncertain")
                # No user name, PIN, or operation details are persisted in HA options.
                return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required("name"): str,
            vol.Required("pin"): PASSWORD,
            vol.Required("pin_confirm"): PASSWORD,
        }), errors=errors)
