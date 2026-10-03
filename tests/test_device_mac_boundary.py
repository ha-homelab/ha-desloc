"""Device.from_json rejects missing or malformed MAC identities from API payloads."""

import pytest

from custom_components.desloc.api import DeslocProtocolError, Device

ROW = {
    "id": 1,
    "mac": "00:11:22:33:44:55",
    "deviceName": "Front door",
    "model": "D110 Plus",
    "batteryValue": 80,
    "networkSignal": -50,
    "doorState": 2,
    "doorStateUpdateTime": 1,
    "onlineStatus": 1,
}


@pytest.mark.parametrize(
    "mac",
    ["", "zz", "00112233445", "00112233445566", "GG:HH:II:JJ:KK:LL", 12345, None],
)
def test_malformed_or_missing_mac_is_rejected(mac):
    with pytest.raises(DeslocProtocolError, match="identity is missing|MAC is malformed"):
        Device.from_json(dict(ROW, mac=mac))


def test_colon_and_dash_mac_normalize():
    assert Device.from_json(ROW).mac == "001122334455"
    assert Device.from_json(dict(ROW, mac="00-11-22-33-44-55")).mac == "001122334455"
