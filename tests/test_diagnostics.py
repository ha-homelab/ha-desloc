"""Compatibility reports must not expose identity or credentials."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.desloc.api import Device
from custom_components.desloc.coordinator import DeslocCoordinator
from custom_components.desloc.diagnostics import async_get_config_entry_diagnostics
from custom_components.desloc.entity import DeslocEntity


@pytest.mark.parametrize("model,validation", [("C100 Plus", "tested"), ("D110 Plus", "experimental")])
async def test_allowlisted_diagnostics(hass, entry, row, model, validation):
    device = Device.from_json(dict(row, model=model, deviceName="private door name"))
    entry.runtime_data = SimpleNamespace(data=device, last_update_success=True)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["device"]["model"] == model
    assert result["device"]["model_validation"] == validation
    assert result["last_poll_success"] is True
    encoded = json.dumps(result)
    for private_value in ("test-secret", "test-phone", "001122334455", "00:11:22:33:44:55",
                          "private door name", entry.entry_id):
        assert private_value not in encoded
    assert not {"id", "mac", "name", "credentials", "token", "pin"} & result["device"].keys()


async def test_unloaded_diagnostics(hass, entry):
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result == {"last_poll_success": False, "device_present": False, "device": None}


async def test_unknown_model_is_visible_but_not_claimed_tested(hass, entry, row):
    coordinator = DeslocCoordinator(hass, entry, AsyncMock())
    coordinator.async_set_updated_data(Device.from_json(dict(row, model="D110 Plus")))
    entity = DeslocEntity(coordinator, "lock")
    assert entity.device_info["model"] == "D110 Plus"
    assert entity.extra_state_attributes == {"model_validation": "experimental"}
    await coordinator.async_shutdown()
