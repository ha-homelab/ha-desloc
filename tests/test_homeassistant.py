from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.desloc.api import Credentials, DeslocAuthError, DeslocConnectionError, Device
from custom_components.desloc.config_flow import DeslocConfigFlow
from custom_components.desloc.coordinator import DeslocCoordinator
from custom_components.desloc.sensor import DESCRIPTIONS, DeslocSensor


async def test_coordinator_disappearing_device_and_sensor(hass, entry, row):
    api = AsyncMock()
    device = Device.from_json(row)
    api.async_devices.return_value = [device]
    coordinator = DeslocCoordinator(hass, entry, api)
    coordinator.async_set_updated_data(await coordinator._async_update_data())
    sensor = DeslocSensor(coordinator, DESCRIPTIONS[0])
    assert sensor.native_value == 55
    assert sensor.available
    assert sensor.unique_id == "001122334455_battery"
    api.async_devices.return_value = []
    coordinator.async_set_updated_data(await coordinator._async_update_data())
    assert sensor.native_value is None
    assert not sensor.available
    await coordinator.async_shutdown()


async def test_coordinator_errors(hass, entry):
    api = AsyncMock()
    coordinator = DeslocCoordinator(hass, entry, api)
    api.async_devices.side_effect = DeslocAuthError("Expired")
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
    api.async_devices.side_effect = DeslocConnectionError("No connection")
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_config_flow_selects_actual_device(hass, row):
    flow = DeslocConfigFlow()
    flow.hass = hass
    flow.context = {"source": "user"}
    with patch("custom_components.desloc.config_flow.async_get_clientsession"), patch(
        "custom_components.desloc.config_flow.DeslocClient.async_devices", return_value=[Device.from_json(row)]
    ):
        result = await flow.async_step_session({"token": "test-secret", "app_device_id": "test-phone"})
    assert result["step_id"] == "device"
    result = await flow.async_step_device({"device_id": "123"})
    assert result["type"] == "create_entry"
    assert result["data"]["mac"] == "001122334455"
    assert result["data"]["device_id"] == 123


async def test_config_flow_invalid_session(hass):
    flow = DeslocConfigFlow()
    flow.hass = hass
    flow.context = {"source": "user"}
    result = await flow.async_step_session({"token": "", "app_device_id": "test-phone"})
    assert result["errors"] == {"base": "invalid_session"}
    with patch("custom_components.desloc.config_flow.async_get_clientsession"), patch(
        "custom_components.desloc.config_flow.DeslocClient.async_devices", side_effect=DeslocAuthError()
    ):
        result = await flow.async_step_session({"token": "test-secret", "app_device_id": "test-phone"})
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_cannot_switch_lock(hass, entry, row):
    flow = DeslocConfigFlow()
    flow.hass = hass
    flow.context = {"source": "reauth"}
    with patch.object(flow, "_get_reauth_entry", return_value=entry), patch(
        "custom_components.desloc.config_flow.async_get_clientsession"
    ), patch("custom_components.desloc.config_flow.DeslocClient.async_devices", return_value=[
        Device.from_json(dict(row, mac="AA:BB:CC:DD:EE:FF"))
    ]):
        result = await flow.async_step_reauth_confirm({"token": "new-secret", "app_device_id": "new-phone"})
    assert result["reason"] == "device_mismatch"


async def test_reauth_updates_session_and_reloads(hass, entry, row):
    flow = DeslocConfigFlow()
    flow.hass = hass
    flow.context = {"source": "reauth"}
    with patch.object(flow, "_get_reauth_entry", return_value=entry), patch.object(
        flow, "async_update_reload_and_abort", return_value={"type": "abort", "reason": "reauth_successful"}
    ) as update, patch("custom_components.desloc.config_flow.async_get_clientsession"), patch(
        "custom_components.desloc.config_flow.DeslocClient.async_devices", return_value=[Device.from_json(row)]
    ):
        result = await flow.async_step_reauth_confirm({"token": "new-secret", "app_device_id": "new-phone"})
    assert result["reason"] == "reauth_successful"
    assert update.call_args.kwargs["data_updates"]["credentials"]["token"] == "new-secret"


async def test_full_setup_entities_and_unload(hass, row):
    """Load the real custom component through HA's flow and platform machinery."""
    from homeassistant import loader
    from homeassistant.bootstrap import async_load_base_functionality

    Path(hass.config.path("custom_components")).symlink_to(
        Path(__file__).resolve().parents[1] / "custom_components", target_is_directory=True
    )
    loader.async_setup(hass)
    assert await async_load_base_functionality(hass)
    async def devices(self):
        if self._account is not None:
            self._credentials = Credentials("account-session", self._account.app_device_id)
        return [Device.from_json(row)]

    with patch(
        "custom_components.desloc.config_flow.async_get_clientsession", new=lambda hass: None
    ), patch("custom_components.desloc.async_get_clientsession", new=lambda hass: None), patch(
        "custom_components.desloc.api.DeslocClient.async_devices", new=devices
    ):
        result = await hass.config_entries.flow.async_init("desloc", context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "session"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {
            "token": "test-secret", "app_device_id": "test-phone",
        })
        assert result["step_id"] == "device"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device_id": "123"})
        assert result["type"] == "create_entry"
        await hass.async_block_till_done()
        states = hass.states.async_all("sensor")
        assert sorted(state.state for state in states) == ["-41", "55"]
        assert [state.state for state in hass.states.async_all("lock")] == ["locked"]
        entry = result["result"]
        original_entities = {state.entity_id for state in hass.states.async_all()
                             if state.domain in ("sensor", "lock")}
        # Exercise the real migration/reload path, including account dataclass
        # reconstruction and entity registry identity preservation.
        reconfigure = await hass.config_entries.flow.async_init("desloc", context={
            "source": "reconfigure", "entry_id": entry.entry_id,
        })
        reconfigure = await hass.config_entries.flow.async_configure(
            reconfigure["flow_id"], {"next_step_id": "account"})
        reconfigure = await hass.config_entries.flow.async_configure(reconfigure["flow_id"], {
            "username": "user@example.invalid", "password": "test-password",
        })
        assert reconfigure["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()
        assert entry.data["auth_type"] == "account"
        assert set(entry.data["credentials"]) == {
            "token", "app_device_id", "app_version", "sys_type"}
        installation = entry.data["credentials"]["app_device_id"]
        assert installation != "test-phone"
        assert entry.runtime_data.client._account is None
        assert entry.runtime_data.client.session_credentials.app_device_id == installation
        assert entry.runtime_data.client.session_credentials.token == "account-session"
        assert {state.entity_id for state in hass.states.async_all()
                if state.domain in ("sensor", "lock")} == original_entities
        assert [state.state for state in hass.states.async_all("lock")] == ["locked"]
        with patch.object(entry.runtime_data, "async_add_pin_user", new=AsyncMock()) as add_pin:
            options = await hass.config_entries.options.async_init(entry.entry_id)
            assert options["step_id"] == "init"
            options = await hass.config_entries.options.async_configure(options["flow_id"], {
                "name": "Synthetic guest", "pin": "825194", "pin_confirm": "825194",
            })
            assert options["type"] == "create_entry" and options["data"] == {}
            add_pin.assert_awaited_once_with("Synthetic guest", "825194")
            assert entry.options == {}
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert all(state.state == "unavailable" for state in hass.states.async_all("sensor"))
