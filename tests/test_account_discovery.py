"""Real HA flow coverage for automatic account-wide lock setup."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.config_entries import ConfigEntryDisabler, SOURCE_IGNORE, SOURCE_SYSTEM

from custom_components.desloc.api import Credentials, Device
from custom_components.desloc.discovery import ValidatedDevice


@pytest.fixture
async def account_environment(hass, row):
    Path(hass.config.path("custom_components")).symlink_to(
        Path(__file__).resolve().parents[1] / "custom_components", target_is_directory=True)
    loader.async_setup(hass)
    assert await async_load_base_functionality(hass)
    rows = [row, dict(row, id=456, mac="00:11:22:33:44:66", deviceName="Second lock",
                      model="D110 Plus", doorState=1, batteryValue=71)]

    async def devices(client):
        await asyncio.sleep(0)
        assert client._account is None
        return [Device.from_json(item) for item in rows]

    forbidden = AsyncMock(side_effect=AssertionError("Discovery must not log in or write to a lock"))
    with patch("custom_components.desloc.config_flow.async_get_clientsession", new=lambda hass: None), patch(
        "custom_components.desloc.async_get_clientsession", new=lambda hass: None,
    ), patch("custom_components.desloc.api.DeslocClient.async_devices", new=devices), patch(
        "custom_components.desloc.api.DeslocClient._login", new=forbidden,
    ), patch("custom_components.desloc.api.DeslocClient.async_switch_lock", new=forbidden), patch(
        "custom_components.desloc.api.DeslocClient.async_create_access_user", new=forbidden,
    ), patch("custom_components.desloc.api.DeslocClient.async_add_pin", new=forbidden):
        yield hass, rows
        forbidden.assert_not_awaited()


async def setup_session(hass, token="first-session", *, entry=None, source="user"):
    context = {"source": source}
    if entry is not None:
        context["entry_id"] = entry.entry_id
    result = await hass.config_entries.flow.async_init(
        "desloc", context=context, data=entry.data if source == "reauth" else None)
    if source != "reauth":
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {
            "next_step_id": "session"})
    return await hass.config_entries.flow.async_configure(result["flow_id"], {
        "token": token, "app_device_id": "synthetic-installation"})


async def test_all_returned_models_and_duplicates_create_independent_entries(account_environment):
    hass, rows = account_environment
    rows.append(dict(rows[0]))
    result = await setup_session(hass)
    assert result["reason"] == "devices_added"
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries("desloc")
    assert len(entries) == 2
    assert {entry.source for entry in entries} == {SOURCE_SYSTEM}
    by_mac = {entry.data["mac"]: entry for entry in entries}
    first, second = by_mac["001122334455"], by_mac["001122334466"]
    assert first.runtime_data.is_locked is True
    assert second.runtime_data.is_locked is False
    assert second.runtime_data.data.model == "D110 Plus"
    assert first.runtime_data._command_lock is not second.runtime_data._command_lock
    assert len(hass.states.async_all("lock")) == 2
    assert {state.state for state in hass.states.async_all("lock")} == {"locked", "unlocked"}
    assert all(entry.data["credentials"]["token"] == "first-session" for entry in entries)


async def test_reconfigure_adds_new_lock_and_reauth_refreshes_peers(account_environment):
    hass, rows = account_environment
    second_row = rows.pop()
    await setup_session(hass)
    await hass.async_block_till_done()
    first = hass.config_entries.async_entries("desloc")[0]
    old_entity_ids = {state.entity_id for state in hass.states.async_all()
                      if state.domain in ("lock", "sensor")}
    rows.append(second_row)
    result = await setup_session(hass, "second-session", entry=first, source="reconfigure")
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries("desloc")
    assert len(entries) == 2
    assert first in entries
    assert old_entity_ids <= {state.entity_id for state in hass.states.async_all()}
    assert all(entry.runtime_data.client.session_credentials.token == "second-session" for entry in entries)
    second = next(entry for entry in entries if entry is not first)
    stale = await hass.config_entries.flow.async_init("desloc", context={
        "source": "reauth", "entry_id": second.entry_id}, data=second.data)
    assert stale["step_id"] == "reauth_confirm"
    result = await setup_session(hass, "third-session", entry=first, source="reauth")
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    assert all(entry.data["credentials"]["token"] == "third-session" for entry in entries)
    assert all(entry.runtime_data.client.session_credentials.token == "third-session" for entry in entries)
    assert stale["flow_id"] not in {flow["flow_id"] for flow in hass.config_entries.flow.async_progress()}


async def test_wrong_account_does_not_update_or_create_entries(account_environment):
    hass, rows = account_environment
    second_row = rows.pop()
    await setup_session(hass)
    await hass.async_block_till_done()
    first = hass.config_entries.async_entries("desloc")[0]
    saved = dict(first.data)
    rows[:] = [second_row]
    result = await setup_session(hass, "wrong-session", entry=first, source="reconfigure")
    assert result["reason"] == "device_mismatch"
    assert hass.config_entries.async_entries("desloc") == [first]
    assert dict(first.data) == saved


async def test_concurrent_account_setup_does_not_duplicate_locks(account_environment):
    hass, rows = account_environment
    results = await asyncio.gather(setup_session(hass), setup_session(hass))
    assert sorted(result["reason"] for result in results) == ["devices_added", "devices_updated"]
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries("desloc")
    assert len(entries) == len({entry.unique_id for entry in entries}) == 2
    assert len(hass.states.async_all("lock")) == 2


async def test_disabled_and_ignored_locks_are_not_reenabled_or_duplicated(account_environment):
    hass, rows = account_environment
    await setup_session(hass)
    await hass.async_block_till_done()
    first, second = hass.config_entries.async_entries("desloc")
    await hass.config_entries.async_set_disabled_by(second.entry_id, ConfigEntryDisabler.USER)
    ignored = await hass.config_entries.flow.async_init("desloc", context={"source": SOURCE_IGNORE}, data={
        "unique_id": "001122334477", "title": "Ignored lock"})
    rows.append(dict(rows[0], id=789, mac="00:11:22:33:44:77"))
    result = await setup_session(hass, "replacement-session", entry=first, source="reconfigure")
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries("desloc", include_ignore=True)) == 3
    assert second.disabled_by is ConfigEntryDisabler.USER
    assert second.data["credentials"]["token"] == "replacement-session"
    assert ignored["result"].source == SOURCE_IGNORE
    assert not ignored["result"].data


async def test_system_flow_rejects_external_or_stale_handoff(account_environment):
    hass, rows = account_environment
    handoff = ValidatedDevice(Device.from_json(rows[0]), Credentials("test-session", "test-installation"), "session")
    for value in (None, {"device_id": 123, "token": "not-validated"}, handoff):
        result = await hass.config_entries.flow.async_init(
            "desloc", context={"source": SOURCE_SYSTEM}, data=value)
        assert result["reason"] == "invalid_discovery"
    assert not hass.config_entries.async_entries("desloc")


async def test_conflicting_cloud_identity_stops_before_any_entry_changes(account_environment):
    hass, rows = account_environment
    rows.append(dict(rows[0], id=999))
    result = await setup_session(hass)
    assert result["errors"] == {"base": "cannot_connect"}
    assert not hass.config_entries.async_entries("desloc")
