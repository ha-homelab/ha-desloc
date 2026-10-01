"""DESLOC business API, based on observed C100 Plus iOS traffic.

This module has no Home Assistant dependency. All requests go to a fixed HTTPS
origin; captured credentials are never forwarded to redirects or other hosts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import aiohttp

BASE_URL = "https://appadmin.desloc.com"
LIST_PATH = "/api/device/list"
LIST_REQUEST = {"groupId": 0, "size": 20}


class DeslocError(Exception):
    """A sanitized API error, without server bodies or credentials."""


class DeslocAuthError(DeslocError):
    """The captured app session has expired or is invalid."""


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
    def __init__(self, session: aiohttp.ClientSession, credentials: Credentials) -> None:
        self._session = session
        self._credentials = credentials

    async def _request(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            async with self._session.post(
                BASE_URL + path, headers=self._credentials.headers(), json=body,
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

    async def _post(self, path: str, body: dict[str, Any]) -> Any:
        payload = await self._request(path, body)
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
        })
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
