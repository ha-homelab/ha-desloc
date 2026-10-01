"""Synthetic login, renewal, concurrency, and interactive authentication tests."""
import asyncio
from collections import deque
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from custom_components.desloc.api import (
    AccountCredentials, Credentials, DeslocAuthError, DeslocCaptchaRequired, DeslocClient,
    DeslocClockError, DeslocInvalidCode, DeslocProtocolError,
    DeslocVerificationRequired, Device,
)
from custom_components.desloc.config_flow import DeslocConfigFlow


def ok(data):
    return {"status": 200, "success": True, "data": data}


def transport(*responses):
    queue = deque(responses)
    session = MagicMock()

    def post(url, **kwargs):
        payload = queue.popleft()
        response = MagicMock(status=200)

        async def json_response():
            await asyncio.sleep(0)  # Exercise concurrent users of the login lock.
            return payload

        response.json = json_response
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=response)
        context.__aexit__ = AsyncMock(return_value=False)
        return context

    session.post.side_effect = post
    account = AccountCredentials.from_password("user@example.invalid", "Example-password!42", "test-installation")
    return DeslocClient(session, account), session, account


CAPTCHA = ok({"isNeedCaptcha": False})
LOGIN = ok({"accessToken": "synthetic-session", "expireIn": 5184000})


def test_password_transform_matches_independent_openssl_vector():
    account = AccountCredentials.from_password("user@example.invalid", "Example-password!42", "test-installation")
    with patch("custom_components.desloc.api.time.time_ns", return_value=1700000000123000000):
        assert account.login_body()["password"] == (
            "9cc655a68fc4e9ed60230e995f2b38ba8315855d65852ad8de1eed2585147ec7ee6fee"
            "dafc901eb83b78e300a0643c6a58bc4a3e81c97a5c0d79322ff76dbfd9f9238d09d890d4df9fd5278d958327c9"
        )
    assert "Example-password" not in str(asdict(account))
    assert account.password_hash not in repr(account)
    assert "example.invalid" not in repr(account)


async def test_login_and_device_discovery_use_distinct_token_headers(row):
    api, session, account = transport(CAPTCHA, LOGIN, ok([row]))
    assert (await api.async_devices())[0].id == 123
    calls = session.post.call_args_list
    assert [c.args[0].rsplit("/api/", 1)[1] for c in calls] == [
        "user/login/isNeedCaptcha", "user/login", "device/list"]
    assert calls[0].kwargs["headers"]["authorization"] == ""
    assert calls[2].kwargs["headers"]["authorization"] == "synthetic-session"
    assert all(c.kwargs["allow_redirects"] is False for c in calls)


async def test_concurrent_reads_share_one_login(row):
    api, session, account = transport(CAPTCHA, LOGIN, ok([row]), ok([row]))
    results = await asyncio.gather(api.async_devices(), api.async_devices())
    assert all(r[0].id == 123 for r in results)
    assert sum(c.args[0].endswith("/user/login") for c in session.post.call_args_list) == 1


async def test_rejected_session_stops_without_evicting_mobile_app(row):
    api, session, account = transport(CAPTCHA, LOGIN, ok([row]), {"status": 401})
    await api.async_devices()
    for _ in range(3):
        with pytest.raises(DeslocAuthError):
            await api.async_devices()
    assert session.post.call_count == 4
    assert sum(c.args[0].endswith("/user/login") for c in session.post.call_args_list) == 1


async def test_rejected_physical_command_neither_replays_nor_signs_in(row):
    api, session, account = transport(CAPTCHA, LOGIN, ok([row]), {"status": 401})
    await api.async_devices()
    with pytest.raises(DeslocAuthError):
        await api.async_switch_lock(123, unlock=True)
    commands = [c for c in session.post.call_args_list if c.args[0].endswith("/remoteSwitchLock")]
    assert len(commands) == 1
    assert session.post.call_count == 4


async def test_exported_session_reuses_token_without_another_login(row):
    api, session, account = transport(CAPTCHA, LOGIN, ok([row]), ok([row]))
    await api.async_devices()
    saved = asdict(api.session_credentials)
    assert "password_hash" not in saved and "username" not in saved
    reloaded = DeslocClient(session, Credentials(**saved))
    assert (await reloaded.async_devices())[0].is_locked is True
    assert session.post.call_count == 4
    assert reloaded._account is None
    assert session.post.call_args.kwargs["headers"]["authorization"] == "synthetic-session"


async def test_saved_session_rejection_remains_blocked():
    _, session, _ = transport({"status": 401})
    api = DeslocClient(session, Credentials("revoked-session", "test-installation"))
    for _ in range(2):
        with pytest.raises(DeslocAuthError):
            await api.async_devices()
    session.post.assert_called_once()


async def test_legacy_digest_entry_requires_interactive_reauth_without_login(hass):
    from homeassistant.exceptions import ConfigEntryAuthFailed
    from custom_components.desloc import async_setup_entry

    account = AccountCredentials.from_password("user@example.invalid", "test", "test-installation")
    legacy = MagicMock(data={"auth_type": "account", "credentials": asdict(account)})
    with patch("custom_components.desloc.async_get_clientsession") as session:
        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, legacy)
    session.assert_not_called()


async def test_captcha_stops_before_login_and_blocks_background_attempts():
    api, session, account = transport(ok({"isNeedCaptcha": True}))
    for _ in range(2):
        with pytest.raises(DeslocCaptchaRequired):
            await api.async_devices()
    session.post.assert_called_once()


@pytest.mark.parametrize("status,error", [(1103, DeslocVerificationRequired), (1105, DeslocInvalidCode),
    (1101, DeslocAuthError), (1102, DeslocAuthError), (1106, DeslocAuthError), (1109, DeslocClockError)])
async def test_login_errors_are_sanitized(status, error):
    api, session, account = transport(CAPTCHA, {"status": status, "success": False,
                                               "msg": "Example-password!42"})
    with pytest.raises(error) as caught:
        await api.async_devices()
    assert "Example-password" not in str(caught.value)
    assert session.post.call_count == 2


async def test_email_code_completes_login_and_is_not_retained(row):
    api, session, account = transport(CAPTCHA, {"status": 1103}, ok({"flag": 1, "interval": 60}),
        LOGIN, ok([row]))
    with pytest.raises(DeslocVerificationRequired):
        await api.async_devices()
    await api.async_send_verification_code()
    await api.async_login("123456")
    assert (await api.async_devices())[0].id == 123
    code_call = session.post.call_args_list[3]
    assert code_call.kwargs["json"] == {"userName": "user@example.invalid",
        "password": account.password_hash, "code": "123456", "childAgreement": True}
    assert "code" not in asdict(account)


@pytest.mark.parametrize("payload", [ok({}), ok({"accessToken": ""}), ok({"accessToken": 1})])
async def test_login_requires_a_valid_token(payload):
    api, session, account = transport(CAPTCHA, payload)
    with pytest.raises(DeslocProtocolError):
        await api.async_devices()


async def test_account_config_flow_verifies_then_selects_lock(hass, row):
    flow = DeslocConfigFlow()
    flow.hass = hass
    flow.context = {"source": "user"}
    with patch("custom_components.desloc.config_flow.async_get_clientsession"), patch(
        "custom_components.desloc.config_flow.DeslocClient.async_devices",
        side_effect=[DeslocVerificationRequired(), [Device.from_json(row)]],
    ), patch("custom_components.desloc.config_flow.DeslocClient.async_send_verification_code") as send, patch(
        "custom_components.desloc.config_flow.DeslocClient.async_login"
    ) as login, patch("custom_components.desloc.config_flow.DeslocClient.session_credentials",
                      new_callable=PropertyMock, return_value=Credentials("test-session", "test-installation")):
        result = await flow.async_step_account({"username": "user@example.invalid", "password": "test-password"})
        assert result["step_id"] == "verification"
        send.assert_awaited_once()
        result = await flow.async_step_verification({"code": "123456"})
        login.assert_awaited_once_with("123456")
        assert result["step_id"] == "device"
        result = await flow.async_step_device({"device_id": "123"})
    assert result["data"]["auth_type"] == "account"
    assert "password" not in result["data"]["credentials"]
    assert "password_hash" not in result["data"]["credentials"]
    assert "123456" not in str(result["data"])


async def test_reconfigure_rejects_another_lock(hass, entry, row):
    flow = DeslocConfigFlow()
    flow.hass = hass
    flow.context = {"source": "reconfigure"}
    with patch.object(flow, "_get_reconfigure_entry", return_value=entry), patch(
        "custom_components.desloc.config_flow.async_get_clientsession"
    ), patch("custom_components.desloc.config_flow.DeslocClient.async_devices",
             return_value=[Device.from_json(dict(row, mac="aabbccddeeff"))]):
        result = await flow.async_step_account({"username": "user@example.invalid", "password": "test-password"})
    assert result["reason"] == "device_mismatch"
