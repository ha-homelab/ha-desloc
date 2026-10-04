"""DESLOC cloud integration, with the C100 Plus protocol physically tested."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .account import async_release_account, get_account
from .api import Credentials
from .const import CONF_CREDENTIALS
from .coordinator import DeslocCoordinator

PLATFORMS = [Platform.LOCK, Platform.SENSOR]
type DeslocConfigEntry = ConfigEntry[DeslocCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DeslocConfigEntry) -> bool:
    saved = entry.data[CONF_CREDENTIALS]
    if "password_hash" in saved or "token" not in saved:
        # Version 0.2.0 retained a digest and signed in during every reload.
        # Do not run that login during upgrade: it can evict the phone app.
        raise ConfigEntryAuthFailed("Sign in again or import the app session to save a reusable DESLOC token")
    credentials = Credentials(**saved)
    account = get_account(hass, async_get_clientsession(hass), credentials)
    # HA also invokes these callbacks after a failed or cancelled setup.
    entry.async_on_unload(lambda: async_release_account(hass, credentials, account))
    entry.runtime_data = DeslocCoordinator(hass, entry, account.client, account=account)
    await entry.runtime_data.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DeslocConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
