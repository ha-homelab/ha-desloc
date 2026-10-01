"""DESLOC account login, email verification, and captured-session fallback."""
from dataclasses import asdict
from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import (AccountCredentials, Credentials, DeslocAuthError, DeslocCaptchaRequired,
    DeslocClient, DeslocClockError, DeslocError, DeslocInvalidCode, DeslocVerificationRequired, Device)
from .const import CONF_CREDENTIALS, CONF_DEVICE_ID, CONF_MAC, DOMAIN

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

    def __init__(self) -> None:
        self._credentials: Credentials | AccountCredentials | None = None
        self._client: DeslocClient | None = None
        self._devices: list[Device] = []
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
        self._devices = [device for device in devices if device.model == "C100 Plus"]
        entry = self._target_entry()
        if entry is not None:
            device = next((d for d in self._devices if d.mac == entry.data[CONF_MAC]), None)
            if device is None:
                return self.async_abort(reason="device_mismatch")
            return self.async_update_reload_and_abort(entry, data_updates={
                CONF_CREDENTIALS: asdict(self._credentials), CONF_DEVICE_ID: device.id,
                "auth_type": "account" if isinstance(self._credentials, AccountCredentials) else "session",
            })
        if not self._devices:
            return self.async_abort(reason="no_devices")
        return await self.async_step_device()

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

    async def async_step_device(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        choices = {str(d.id): f"{d.name} ({d.model})" for d in self._devices}
        errors = {}
        if user_input is not None:
            device = next((d for d in self._devices if str(d.id) == user_input.get(CONF_DEVICE_ID)), None)
            if device is None:
                errors["base"] = "no_devices"
            else:
                await self.async_set_unique_id(device.mac)
                self._abort_if_unique_id_configured()
                assert self._credentials is not None
                return self.async_create_entry(title=device.name, data={
                    CONF_CREDENTIALS: asdict(self._credentials),
                    "auth_type": "account" if isinstance(self._credentials, AccountCredentials) else "session",
                    CONF_DEVICE_ID: device.id, CONF_MAC: device.mac,
                })
        return self.async_show_form(step_id="device", data_schema=vol.Schema({
            vol.Required(CONF_DEVICE_ID): vol.In(choices),
        }), errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        if entry_data.get("auth_type") == "account":
            return await self.async_step_account()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._session_step("reauth_confirm", user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self.async_step_user()
