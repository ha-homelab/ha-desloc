"""DESLOC business API, based on observed C100 Plus iOS traffic.

This module has no Home Assistant dependency. All requests go to a fixed HTTPS
origin; captured credentials are never forwarded to redirects or other hosts.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
import re
import time
from typing import Any
from urllib.parse import quote

import aiohttp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

BASE_URL = "https://appadmin.desloc.com"
LIST_PATH = "/api/device/list"
LIST_REQUEST = {"groupId": 0, "size": 20}


class DeslocError(Exception):
    """A sanitized API error, without server bodies or credentials."""


class DeslocAuthError(DeslocError):
    """Credentials were rejected or interactive authentication is required."""


class DeslocVerificationRequired(DeslocAuthError):
    """DESLOC requires an email code for this app installation."""


class DeslocCaptchaRequired(DeslocAuthError):
    """Complete the vendor's CAPTCHA in the official app."""


class DeslocInvalidCode(DeslocAuthError):
    """The email verification code was rejected."""


class DeslocClockError(DeslocError):
    """The server rejected the client clock."""


class DeslocConnectionError(DeslocError):
    """The server could not be reached."""


class DeslocProtocolError(DeslocError):
    """The server returned an unsupported response."""


class DeslocCommandTimeout(DeslocError):
    """The cloud no longer has a confirmed result for the command."""


@dataclass(frozen=True)
class Credentials:
    token: str = field(repr=False)
    app_device_id: str = field(repr=False)
    app_version: str = "1.2.1"
    sys_type: str = "1"

    def __post_init__(self) -> None:
        for value in (self.token, self.app_device_id, self.app_version, self.sys_type):
            if not isinstance(value, str) or not value.strip() or "\r" in value or "\n" in value:
                raise ValueError("Session fields must be non-empty single-line strings")

    def headers(self) -> dict[str, str]:
        return {"authorization": self.token, "deviceid": self.app_device_id,
                "appversion": self.app_version, "systype": self.sys_type}


@dataclass(frozen=True)
class AccountCredentials:
    """A password-equivalent digest, never a plaintext account password."""

    username: str = field(repr=False)
    password_hash: str = field(repr=False)
    app_device_id: str = field(repr=False)
    app_version: str = "1.2.1"
    sys_type: str = "1"

    def __post_init__(self) -> None:
        Credentials("validation", self.app_device_id, self.app_version, self.sys_type)
        if not isinstance(self.username, str) or not self.username.strip():
            raise ValueError("Account email is required")
        if not isinstance(self.password_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", self.password_hash):
            raise ValueError("Invalid password digest")

    @classmethod
    def from_password(cls, username: str, password: str, app_device_id: str) -> AccountCredentials:
        if not isinstance(username, str) or not isinstance(password, str) or not password:
            raise ValueError("Account password is required")
        digest = hashlib.sha256((password + "DEqFDHCkeOMGEZAq").encode()).hexdigest()
        return cls(username.strip(), digest, app_device_id)

    def headers(self) -> dict[str, str]:
        return {"authorization": "", "deviceid": self.app_device_id,
                "appversion": self.app_version, "systype": self.sys_type}

    def login_body(self, code: str | None = None) -> dict[str, Any]:
        if code is not None:
            if not isinstance(code, str) or not code.strip() or len(code) > 64:
                raise ValueError("Verification code is required")
            # The app sends the digest directly when completing email verification.
            password = self.password_hash
        else:
            # Wire compatibility with the app, inside TLS; this is not secret storage.
            plaintext = (self.password_hash + str(time.time_ns() // 1_000_000)).encode()
            padder = PKCS7(128).padder()
            padded = padder.update(plaintext) + padder.finalize()
            encryptor = Cipher(algorithms.AES(b"2897ab5600b54465b5ea0a89d9a192c7"),
                               modes.CBC(bytes(16))).encryptor()
            password = (encryptor.update(padded) + encryptor.finalize()).hex()
        body = {"userName": self.username, "password": password, "childAgreement": True}
        if code is not None:
            body["code"] = code.strip()
        return body


def integer(value: Any) -> int | None:
    """Do not coerce booleans or strings into documented numeric fields."""
    return value if type(value) is int else None


@dataclass(frozen=True)
class Device:
    id: int
    mac: str
    name: str
    model: str
    firmware: str | None
    battery: int | None
    rssi: int | None
    door_state: int | None
    door_state_updated_ms: int | None
    online_status: int | None

    @property
    def is_locked(self) -> bool | None:
        # Observed during the user's unlock/lock cycle with Bluetooth disabled.
        return {1: False, 2: True}.get(self.door_state)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Device:
        identity = integer(data.get("id"))
        mac = data.get("mac")
        if identity is None or not isinstance(mac, str):
            raise DeslocProtocolError("Device identity is missing")
        compact_mac = mac.replace(":", "").replace("-", "").lower()
        if len(compact_mac) != 12 or any(c not in "0123456789abcdef" for c in compact_mac):
            raise DeslocProtocolError("Device MAC is malformed")
        battery = integer(data.get("batteryValue"))
        if battery is not None and not 0 <= battery <= 100:
            battery = None
        rssi = integer(data.get("networkSignal"))
        if rssi is not None and not -127 <= rssi <= 0:
            rssi = None
        return cls(identity, compact_mac,
                   str(data.get("deviceName") or data.get("model") or "DESLOC"),
                   str(data.get("model") or "Unknown"),
                   data.get("firmwareVersion") if isinstance(data.get("firmwareVersion"), str) else None,
                   battery, rssi, integer(data.get("doorState")),
                   integer(data.get("doorStateUpdateTime")), integer(data.get("onlineStatus")))


class DeslocClient:
    def __init__(self, session: aiohttp.ClientSession, credentials: Credentials | AccountCredentials) -> None:
        self._session = session
        self._account = credentials if isinstance(credentials, AccountCredentials) else None
        self._credentials = credentials if isinstance(credentials, Credentials) else None
        self._login_lock = asyncio.Lock()
        self._auth_blocked: DeslocAuthError | None = None

    async def _raw_request(self, path: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        try:
            async with self._session.post(
                BASE_URL + path, headers=headers, json=body,
                timeout=aiohttp.ClientTimeout(total=15), allow_redirects=False,
            ) as response:
                if response.status in (401, 403):
                    raise DeslocAuthError("DESLOC session was rejected")
                if response.status != 200:
                    raise DeslocProtocolError(f"DESLOC HTTP status {response.status}")
                payload = await response.json()
        except (aiohttp.ClientError, TimeoutError):
            raise DeslocConnectionError("DESLOC request failed") from None
        except ValueError:
            raise DeslocProtocolError("DESLOC response is not JSON") from None
        if not isinstance(payload, dict):
            raise DeslocProtocolError("DESLOC response is not an object")
        # Business API returns authentication errors inside HTTP 200 responses.
        if payload.get("status") in (401, 403):
            raise DeslocAuthError("DESLOC session was rejected")
        return payload

    async def _login(self, code: str | None = None) -> None:
        assert self._account is not None
        account = self._account
        headers = account.headers()
        if code is None:
            captcha = await self._raw_request("/api/user/login/isNeedCaptcha",
                                               {"userName": account.username}, headers)
            data = captcha.get("data")
            if captcha.get("status") != 200 or captcha.get("success") is not True or not isinstance(data, dict):
                raise DeslocProtocolError("Cannot check DESLOC login requirements")
            if data.get("isNeedCaptcha") is True:
                raise DeslocCaptchaRequired("Complete CAPTCHA in the DESLOC app")
            if data.get("isNeedCaptcha") is not False:
                raise DeslocProtocolError("Invalid CAPTCHA requirement response")
        result = await self._raw_request("/api/user/login", account.login_body(code), headers)
        status = result.get("status")
        if status == 1103:
            raise DeslocVerificationRequired("Email verification is required")
        if status == 1105:
            raise DeslocInvalidCode("Verification code was rejected")
        if status in (1101, 1102, 1106):
            raise DeslocAuthError("DESLOC account login was rejected")
        if status == 1109:
            raise DeslocClockError("Synchronize the Home Assistant system clock")
        data = result.get("data")
        if status != 200 or result.get("success") is not True or not isinstance(data, dict):
            raise DeslocProtocolError("DESLOC login failed")
        try:
            credentials = Credentials(data.get("accessToken"), account.app_device_id,
                                      account.app_version, account.sys_type)
        except ValueError:
            raise DeslocProtocolError("DESLOC login returned an invalid session") from None
        self._credentials = credentials
        self._auth_blocked = None

    async def async_login(self, code: str | None = None) -> None:
        """Explicit setup/reauth attempt; a code is never retained."""
        async with self._login_lock:
            try:
                await self._login(code)
            except DeslocAuthError as error:
                self._credentials = None
                self._auth_blocked = error
                raise

    async def async_send_verification_code(self) -> None:
        assert self._account is not None
        result = await self._raw_request("/api/user/login/sendCode",
            {"userName": self._account.username}, self._account.headers())
        data = result.get("data")
        if (result.get("status") != 200 or result.get("success") is not True
                or not isinstance(data, dict) or integer(data.get("flag")) != 1):
            raise DeslocProtocolError("DESLOC could not send a verification code; try again later")

    async def _ensure_session(self, rejected: Credentials | None = None) -> None:
        if self._account is None:
            return
        async with self._login_lock:
            if self._auth_blocked is not None:
                raise self._auth_blocked
            if self._credentials is not None and self._credentials is not rejected:
                return
            self._credentials = None
            try:
                await self._login()
            except DeslocAuthError as error:
                self._auth_blocked = error
                raise

    async def _request(self, path: str, body: dict[str, Any], *, safe_read: bool = True) -> dict[str, Any]:
        await self._ensure_session()
        assert self._credentials is not None
        credentials = self._credentials
        try:
            return await self._raw_request(path, body, credentials.headers())
        except DeslocAuthError:
            if self._account is None:
                raise
            await self._ensure_session(rejected=credentials)
            if not safe_read:
                raise DeslocError("Session renewed; check the lock before requesting another command") from None
            assert self._credentials is not None
            return await self._raw_request(path, body, self._credentials.headers())

    async def _post(self, path: str, body: dict[str, Any], *, safe_read: bool = True) -> Any:
        payload = await self._request(path, body, safe_read=safe_read)
        if payload.get("status") != 200 or payload.get("success") is not True:
            raise DeslocProtocolError("DESLOC rejected the request")
        return payload.get("data")

    async def async_devices(self) -> list[Device]:
        data = await self._post(LIST_PATH, LIST_REQUEST)
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise DeslocProtocolError("DESLOC device list is malformed")
        return [Device.from_json(row) for row in data]

    async def async_switch_lock(self, device_id: int, *, unlock: bool) -> str:
        """Send exactly once. A returned ID indicates acceptance, not bolt state."""
        if type(device_id) is not int or type(unlock) is not bool:
            raise ValueError("Invalid command arguments")
        data = await self._post("/api/device/remoteSwitchLock", {
            "deviceId": str(device_id), "unlock": unlock,
        }, safe_read=False)
        command_id = data.get("commandId") if isinstance(data, dict) else None
        if not isinstance(command_id, str) or not command_id or len(command_id) > 256:
            raise DeslocProtocolError("Command accepted without a usable result ID; check the lock")
        return command_id

    async def async_command_complete(self, command_id: str) -> bool:
        """Read the result of an existing command; never reissue the command."""
        payload = await self._request("/api/device/fecommand/result/" + quote(command_id, safe=""), {})
        if payload.get("status") == 2206 and payload.get("success") is False:
            return False
        if payload.get("status") == 2104:
            raise DeslocCommandTimeout("Device command result expired; check the lock")
        if payload.get("status") == 200 and payload.get("success") is True:
            return True
        raise DeslocProtocolError("Device command failed; check the lock")
