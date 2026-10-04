"""Synthetic access-management tests; no real PINs or cloud calls."""
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.config_entries import ConfigEntry

from custom_components.desloc.api import (
    DeslocAuthError, DeslocConnectionError, DeslocProtocolError, DeslocUserExists,
    Device, encrypt_vendor_text, validate_pin_user,
)
from custom_components.desloc.config_flow import DeslocOptionsFlow
from custom_components.desloc.coordinator import DeslocCoordinator, DeslocPinPreflightFailed


def test_pin_cipher_matches_independent_openssl_vector():
    assert encrypt_vendor_text("825194") == "a522e8d94658a4677a019acec0c1e98c"


@pytest.mark.parametrize("pin", ["", "12345", "123456789", "１２３４５６", "12a456", 825194])
def test_pin_validation_preserves_ascii_and_length_rules(pin):
    with pytest.raises(ValueError):
        validate_pin_user("Synthetic guest", pin)


@pytest.mark.parametrize("name", ["", " ", "x" * 25, "Guest\nName"])
def test_name_fits_both_user_and_pin_label(name):
    with pytest.raises(ValueError):
        validate_pin_user(name, "825194")


async def test_api_creates_regular_user_and_encrypts_pin(transport):
    api, session, response, _ = transport
    response.json.return_value = {"status": 200, "success": True, "data": {
        "id": 456, "deviceId": 123, "accessType": 1, "accessName": "Synthetic guest"}}
    assert await api.async_create_access_user(123, "Synthetic guest") == 456
    assert session.post.call_args.kwargs["json"] == {
        "deviceId": "123", "accessType": 1, "userName": "Synthetic guest"}
    response.json.return_value = {"status": 200, "success": True, "data": {"commandId": "synthetic-pin-command"}}
    assert await api.async_add_pin(456, "Synthetic guest", "825194") == "synthetic-pin-command"
    body = session.post.call_args.kwargs["json"]
    assert body == {"accessId": "456", "keyName": "Synthetic guest",
                    "password": "a522e8d94658a4677a019acec0c1e98c"}
    assert "825194" not in str(body)


async def test_api_rejects_creation_for_another_device(transport):
    api, session, response, _ = transport
    response.json.return_value = {"status": 200, "success": True, "data": {
        "id": 456, "deviceId": 999, "accessType": 1, "accessName": "Synthetic guest"}}
    with pytest.raises(DeslocProtocolError):
        await api.async_create_access_user(123, "Synthetic guest")
    session.post.assert_called_once()


async def test_api_requires_installed_pin_on_the_expected_user(transport):
    api, session, response, _ = transport
    data = {"id": 456, "deviceId": 123, "accessType": 1, "status": 1, "updateFlag": 0,
            "keys": [{"keyType": 1, "updateFlag": 0, "passwordName": "Synthetic guest"}]}
    response.json.return_value = {"status": 200, "success": True, "data": data}
    assert await api.async_pin_present(456, 123, "Synthetic guest")
    data["keys"][0]["updateFlag"] = 1
    assert not await api.async_pin_present(456, 123, "Synthetic guest")
    data["id"] = 789
    with pytest.raises(DeslocProtocolError):
        await api.async_pin_present(456, 123, "Synthetic guest")


def coordinator(hass, entry, row):
    api = AsyncMock()
    api.async_access_users.return_value = []
    api.async_create_access_user.return_value = 456
    api.async_add_pin.return_value = "synthetic-pin-command"
    api.async_command_complete.return_value = True
    api.async_pin_present.return_value = True
    result = DeslocCoordinator(hass, entry, api)
    result.async_set_updated_data(Device.from_json(row))
    return result, api


async def test_create_pin_waits_for_command_and_user_confirmation(hass, entry, row):
    coord, api = coordinator(hass, entry, row)
    api.async_command_complete.side_effect = [False, True]
    api.async_pin_present.side_effect = [False, True]
    with patch("custom_components.desloc.coordinator.asyncio.sleep", new=AsyncMock()):
        await coord.async_add_pin_user(" Synthetic guest ", "825194")
    api.async_create_access_user.assert_awaited_once_with(123, "Synthetic guest")
    api.async_add_pin.assert_awaited_once_with(456, "Synthetic guest", "825194")
    assert api.async_command_complete.await_count == 2
    assert api.async_pin_present.await_count == 2
    api.async_switch_lock.assert_not_awaited()
    assert not coord._command_lock.locked()
    await coord.async_shutdown()


async def test_duplicate_user_never_writes(hass, entry, row):
    coord, api = coordinator(hass, entry, row)
    api.async_access_users.return_value = [{"id": 456, "accessName": "SYNTHETIC GUEST"}]
    with pytest.raises(DeslocUserExists):
        await coord.async_add_pin_user("Synthetic guest", "825194")
    api.async_pin_present.assert_awaited_once_with(456, 123, "SYNTHETIC GUEST")
    api.async_create_access_user.assert_not_awaited()
    api.async_add_pin.assert_not_awaited()
    await coord.async_shutdown()


@pytest.mark.parametrize("stage", ["async_create_access_user", "async_add_pin", "async_command_complete", "async_pin_present"])
async def test_uncertain_mutation_never_retries_or_deletes(hass, entry, row, stage):
    coord, api = coordinator(hass, entry, row)
    getattr(api, stage).side_effect = DeslocConnectionError("private-server-body")
    with pytest.raises(HomeAssistantError, match="uncertain") as error:
        await coord.async_add_pin_user("Synthetic guest", "825194")
    assert "private-server-body" not in str(error.value) and "825194" not in str(error.value)
    assert api.async_create_access_user.await_count == 1
    assert api.async_add_pin.await_count <= 1
    assert not coord._command_lock.locked()
    await coord.async_shutdown()


async def test_pin_operation_does_not_overlap_a_lock_command(hass, entry, row):
    coord, api = coordinator(hass, entry, row)
    async with coord._command_lock:
        with pytest.raises(HomeAssistantError, match="already in progress"):
            await coord.async_add_pin_user("Synthetic guest", "825194")
    api.async_access_users.assert_not_awaited()
    await coord.async_shutdown()


async def test_options_flow_does_not_persist_pin_or_resubmit(hass):
    flow = DeslocOptionsFlow()
    flow.hass = hass
    runtime = MagicMock(last_update_success=True, data=object())
    runtime.async_add_pin_user = AsyncMock()
    with patch.object(DeslocOptionsFlow, "config_entry", new_callable=PropertyMock,
                      return_value=MagicMock(runtime_data=runtime)):
        result = await flow.async_step_init({"name": "Synthetic guest", "pin": "825194", "pin_confirm": "825194"})
        assert result["type"] == "create_entry" and result["data"] == {}
        assert "825194" not in str(result)
        result = await flow.async_step_init({"name": "Synthetic guest", "pin": "825194", "pin_confirm": "825194"})
        assert result["reason"] == "already_submitted"
    runtime.async_add_pin_user.assert_awaited_once_with("Synthetic guest", "825194")


async def test_options_reject_mismatched_pin_before_operation(hass):
    flow = DeslocOptionsFlow()
    flow.hass = hass
    runtime = MagicMock(last_update_success=True, data=object())
    runtime.async_add_pin_user = AsyncMock()
    with patch.object(DeslocOptionsFlow, "config_entry", new_callable=PropertyMock,
                      return_value=MagicMock(runtime_data=runtime)):
        result = await flow.async_step_init({"name": "Synthetic guest", "pin": "825194", "pin_confirm": "948251"})
    assert result["errors"] == {"base": "pin_mismatch"}
    assert "825194" not in str(result)
    runtime.async_add_pin_user.assert_not_awaited()


async def submit_pin(hass, runtime):
    flow = DeslocOptionsFlow()
    flow.hass = hass
    with patch.object(DeslocOptionsFlow, "config_entry", new_callable=PropertyMock,
                      return_value=MagicMock(runtime_data=runtime)):
        result = await flow.async_step_init({
            "name": "Synthetic guest", "pin": "825194", "pin_confirm": "825194"})
    assert "825194" not in str(result)
    return result


async def test_options_busy_lock_does_not_report_uncertain_write(hass, entry, row):
    coord, api = coordinator(hass, entry, row)
    async with coord._command_lock:
        assert (await submit_pin(hass, coord))["reason"] == "command_in_progress"
    api.async_access_users.assert_not_awaited()
    api.async_create_access_user.assert_not_awaited()
    api.async_add_pin.assert_not_awaited()
    await coord.async_shutdown()


async def test_options_unavailable_lock_does_not_attempt_writes(hass, entry, row):
    coord, api = coordinator(hass, entry, row)
    coord.last_update_success = False
    assert (await submit_pin(hass, coord))["reason"] == "unavailable"
    api.async_access_users.assert_not_awaited()
    api.async_create_access_user.assert_not_awaited()
    api.async_add_pin.assert_not_awaited()
    await coord.async_shutdown()


@pytest.mark.parametrize("stage", ["async_access_users", "async_pin_present"])
async def test_read_failure_before_creation_is_not_an_uncertain_write(hass, entry, row, stage):
    coord, api = coordinator(hass, entry, row)
    if stage == "async_pin_present":
        api.async_access_users.return_value = [{"id": 456, "accessName": "Synthetic guest"}]
    getattr(api, stage).side_effect = DeslocConnectionError("private-server-body")
    assert (await submit_pin(hass, coord))["reason"] == "pin_preflight_failed"
    api.async_create_access_user.assert_not_awaited()
    api.async_add_pin.assert_not_awaited()
    assert not coord._command_lock.locked()
    await coord.async_shutdown()


async def test_preflight_error_is_sanitized(hass, entry, row):
    coord, api = coordinator(hass, entry, row)
    api.async_access_users.side_effect = DeslocProtocolError("private-server-body")
    with pytest.raises(DeslocPinPreflightFailed) as error:
        await coord.async_add_pin_user("Synthetic guest", "825194")
    assert "private-server-body" not in str(error.value)
    assert "825194" not in str(error.value)
    api.async_create_access_user.assert_not_awaited()
    await coord.async_shutdown()


async def test_partial_creation_then_same_name_is_read_only_recovery(hass, entry, row):
    coord, api = coordinator(hass, entry, row)
    api.async_add_pin.side_effect = DeslocConnectionError("Synthetic lost response")
    assert (await submit_pin(hass, coord))["reason"] == "pin_creation_uncertain"
    api.async_access_users.return_value = [{"id": 456, "accessName": "Synthetic guest"}]
    api.async_pin_present.return_value = False
    api.async_create_access_user.reset_mock()
    api.async_add_pin.reset_mock()
    assert (await submit_pin(hass, coord))["reason"] == "existing_user_pin_unconfirmed"
    api.async_pin_present.assert_awaited_once_with(456, 123, "Synthetic guest")
    api.async_create_access_user.assert_not_awaited()
    api.async_add_pin.assert_not_awaited()
    api.async_switch_lock.assert_not_awaited()
    await coord.async_shutdown()


async def test_existing_user_with_confirmed_record_keeps_duplicate_result(hass, entry, row):
    coord, api = coordinator(hass, entry, row)
    api.async_access_users.return_value = [{"id": 456, "accessName": "SYNTHETIC GUEST"}]
    assert (await submit_pin(hass, coord))["reason"] == "user_exists"
    api.async_pin_present.assert_awaited_once_with(456, 123, "SYNTHETIC GUEST")
    api.async_create_access_user.assert_not_awaited()
    api.async_add_pin.assert_not_awaited()
    await coord.async_shutdown()


@pytest.mark.parametrize("stage,reason", [
    ("async_access_users", "pin_preflight_failed"),
    ("async_add_pin", "pin_creation_uncertain"),
])
async def test_auth_revocation_before_and_after_first_write(hass, entry, row, stage, reason):
    coord, api = coordinator(hass, entry, row)
    getattr(api, stage).side_effect = DeslocAuthError("private-server-body")
    with patch.object(ConfigEntry, "async_start_reauth") as reauth:
        assert (await submit_pin(hass, coord))["reason"] == reason
    reauth.assert_called_once_with(hass)
    assert api.async_create_access_user.await_count == (0 if stage == "async_access_users" else 1)
    assert api.async_add_pin.await_count <= 1
    api.async_login.assert_not_awaited()
    await coord.async_shutdown()
