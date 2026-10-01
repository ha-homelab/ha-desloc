"""Set up and renew a captured DESLOC app session."""
from dataclasses import asdict
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import Credentials, DeslocAuthError, DeslocClient, DeslocError, Device
from .const import CONF_CREDENTIALS, CONF_DEVICE_ID, CONF_MAC, DOMAIN

SESSION_SCHEMA = vol.Schema({
    vol.Required("token"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    vol.Required("app_device_id"): str,
    vol.Optional("app_version", default="1.2.1"): str,
    vol.Optional("sys_type", default="1"): str,
})


class DeslocConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._credentials: Credentials | None = None
        self._devices: list[Device] = []

    async def _session_step(self, step_id: str, user_input: dict[str, Any] | None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            try:
                credentials = Credentials(**user_input)
                devices = await DeslocClient(async_get_clientsession(self.hass), credentials).async_devices()
            except (ValueError, TypeError):
                errors["base"] = "invalid_session"
            except DeslocAuthError:
                errors["base"] = "invalid_auth"
            except DeslocError:
                errors["base"] = "cannot_connect"
            else:
                self._credentials = credentials
                self._devices = [device for device in devices if device.model == "C100 Plus"]
                if step_id == "reauth_confirm":
                    entry = self._get_reauth_entry()
                    device = next((d for d in self._devices if d.mac == entry.data[CONF_MAC]), None)
                    if device is None:
                        errors["base"] = "device_mismatch"
                    else:
                        return self.async_update_reload_and_abort(entry, data_updates={
                            CONF_CREDENTIALS: asdict(credentials), CONF_DEVICE_ID: device.id,
                        })
                elif not self._devices:
                    errors["base"] = "no_devices"
                else:
                    return await self.async_step_device()
        return self.async_show_form(step_id=step_id, data_schema=SESSION_SCHEMA, errors=errors)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._session_step("user", user_input)

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
                    CONF_DEVICE_ID: device.id, CONF_MAC: device.mac,
                })
        return self.async_show_form(step_id="device", data_schema=vol.Schema({
            vol.Required(CONF_DEVICE_ID): vol.In(choices),
        }), errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._session_step("reauth_confirm", user_input)
