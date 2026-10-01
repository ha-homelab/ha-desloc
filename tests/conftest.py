"""Synthetic data only; tests never load the private capture or call DESLOC."""
from unittest.mock import AsyncMock, MagicMock
from types import MappingProxyType

import pytest
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.desloc.api import Credentials, DeslocClient


@pytest.fixture
async def hass(tmp_path):
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    yield instance
    await instance.async_stop(force=True)
    await instance.async_block_till_done()


@pytest.fixture
def entry():
    return ConfigEntry(version=1, minor_version=1, domain="desloc", title="Test lock",
        data={"mac": "001122334455", "device_id": 123, "credentials": {
            "token": "test-secret", "app_device_id": "test-phone"}},
        source="user", unique_id="001122334455", options={},
        discovery_keys=MappingProxyType({}), subentries_data=[])


@pytest.fixture
def row():
    return {"id": 123, "mac": "00:11:22:33:44:55", "deviceName": "Test lock",
            "model": "C100 Plus", "batteryValue": 55, "networkSignal": -41,
            "doorState": 2, "doorStateUpdateTime": 1700000000000,
            "onlineStatus": 1, "firmwareVersion": "test-firmware"}


@pytest.fixture
def credentials():
    return Credentials(token="test-secret", app_device_id="test-phone")


@pytest.fixture
def transport(credentials, row):
    response = MagicMock(status=200)
    response.json = AsyncMock(return_value={"status": 200, "success": True, "data": [row]})
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    return DeslocClient(session, credentials), session, response, context
