"""DESLOC C100 Plus cloud integration, derived from a real app capture."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AccountCredentials, Credentials, DeslocClient
from .const import CONF_CREDENTIALS
from .coordinator import DeslocCoordinator

PLATFORMS = [Platform.LOCK, Platform.SENSOR]
type DeslocConfigEntry = ConfigEntry[DeslocCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DeslocConfigEntry) -> bool:
    credentials_type = AccountCredentials if entry.data.get("auth_type") == "account" else Credentials
    client = DeslocClient(async_get_clientsession(hass), credentials_type(**entry.data[CONF_CREDENTIALS]))
    entry.runtime_data = DeslocCoordinator(hass, entry, client)
    await entry.runtime_data.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DeslocConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
