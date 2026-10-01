import aiohttp
import pytest

from custom_components.desloc.api import (
    Credentials, DeslocAuthError, DeslocConnectionError, DeslocProtocolError, Device, DeslocCommandTimeout,
)


async def test_captured_read_format(transport):
    api, session, response, context = transport
    devices = await api.async_devices()
    assert len(devices) == 1
    assert devices[0].mac == "001122334455"
    assert (devices[0].battery, devices[0].rssi, devices[0].door_state) == (55, -41, 2)
    session.post.assert_called_once()
    args, kwargs = session.post.call_args
    assert args == ("https://appadmin.desloc.com/api/device/list",)
    assert kwargs["json"] == {"groupId": 0, "size": 20}
    assert kwargs["headers"] == {"authorization": "test-secret", "deviceid": "test-phone",
                                 "appversion": "1.2.1", "systype": "1"}
    assert kwargs["allow_redirects"] is False


@pytest.mark.parametrize("http_status,business_status", [(401, 200), (403, 200), (200, 401), (200, 403)])
async def test_auth_failure_not_retried(transport, http_status, business_status):
    api, session, response, context = transport
    response.status = http_status
    response.json.return_value = {"status": business_status, "success": False,
                                  "msg": "test-secret should never be logged"}
    with pytest.raises(DeslocAuthError) as error:
        await api.async_devices()
    assert "test-secret" not in str(error.value)
    session.post.assert_called_once()


@pytest.mark.parametrize("status", [302, 404, 429, 500])
async def test_http_failures(transport, status):
    api, session, response, context = transport
    response.status = status
    with pytest.raises(DeslocProtocolError):
        await api.async_devices()
    session.post.assert_called_once()


@pytest.mark.parametrize("payload", [None, [], {"status": 200, "success": False},
    {"status": 400, "success": False, "msg": "test-secret"},
    {"status": 200, "success": True, "data": {}},
    {"status": 200, "success": True, "data": [1]},
    {"status": 200, "success": True, "data": [{}]}])
async def test_malformed_or_rejected_response(transport, payload):
    api, session, response, context = transport
    response.json.return_value = payload
    with pytest.raises(DeslocProtocolError) as error:
        await api.async_devices()
    assert "test-secret" not in str(error.value)


@pytest.mark.parametrize("error", [TimeoutError("test-secret"), aiohttp.ClientConnectionError("test-secret")])
async def test_network_errors_are_sanitized(transport, error):
    api, session, response, context = transport
    context.__aenter__.side_effect = error
    with pytest.raises(DeslocConnectionError) as caught:
        await api.async_devices()
    assert "test-secret" not in str(caught.value)
    session.post.assert_called_once()


async def test_non_json_body(transport):
    api, session, response, context = transport
    response.json.side_effect = ValueError("test-secret")
    with pytest.raises(DeslocProtocolError):
        await api.async_devices()


def test_unknown_states_stay_raw_and_battery_zero_is_valid(row):
    device = Device.from_json(dict(row, batteryValue=0, doorState=987, onlineStatus=987))
    assert device.battery == 0
    assert device.door_state == 987
    assert device.online_status == 987
    assert device.is_locked is None


@pytest.mark.parametrize("code,expected", [(1, False), (2, True), (0, None), (None, None)])
def test_observed_state_mapping(row, code, expected):
    assert Device.from_json(dict(row, doorState=code)).is_locked is expected


@pytest.mark.parametrize("value", [True, "55", -1, 101, None])
def test_invalid_battery_is_unknown(row, value):
    assert Device.from_json(dict(row, batteryValue=value)).battery is None


def test_credentials_do_not_leak_in_repr(credentials):
    assert "test-secret" not in repr(credentials)
    assert "test-phone" not in repr(credentials)
    with pytest.raises(ValueError):
        Credentials(token="injected\r\nheader", app_device_id="test-phone")


@pytest.mark.parametrize("unlock", [False, True])
async def test_command_sent_once_with_observed_format(transport, unlock):
    api, session, response, context = transport
    response.json.return_value = {"status": 200, "success": True, "data": {"commandId": "synthetic-command-1"}}
    assert await api.async_switch_lock(123, unlock=unlock) == "synthetic-command-1"
    session.post.assert_called_once()
    assert session.post.call_args.args == ("https://appadmin.desloc.com/api/device/remoteSwitchLock",)
    assert session.post.call_args.kwargs["json"] == {"deviceId": "123", "unlock": unlock}


@pytest.mark.parametrize("status,success,expected", [(2206, False, False), (200, True, True)])
async def test_command_result_is_a_separate_read(transport, status, success, expected):
    api, session, response, context = transport
    response.json.return_value = {"status": status, "success": success}
    assert await api.async_command_complete("synthetic-command-1") is expected
    session.post.assert_called_once()
    assert session.post.call_args.args[0].endswith("/api/device/fecommand/result/synthetic-command-1")
    assert session.post.call_args.kwargs["json"] == {}


async def test_expired_command_result_never_replays_command(transport):
    api, session, response, context = transport
    response.json.return_value = {"status": 2104, "success": False}
    with pytest.raises(DeslocCommandTimeout):
        await api.async_command_complete("old-command")
    session.post.assert_called_once()
    assert "/remoteSwitchLock" not in session.post.call_args.args[0]


async def test_command_missing_id_is_not_success(transport):
    api, session, response, context = transport
    response.json.return_value = {"status": 200, "success": True, "data": {}}
    with pytest.raises(DeslocProtocolError):
        await api.async_switch_lock(123, unlock=True)
    session.post.assert_called_once()
