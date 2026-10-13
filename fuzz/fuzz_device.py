import json
import sys
import types
from pathlib import Path

import atheris

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("custom_components")
package.__path__ = [str(ROOT / "custom_components")]
sys.modules[package.__name__] = package
package = types.ModuleType("custom_components.desloc")
package.__path__ = [str(ROOT / "custom_components/desloc")]
sys.modules[package.__name__] = package

with atheris.instrument_imports():
    from custom_components.desloc.api import DeslocProtocolError, Device


def test_one_input(data: bytes) -> None:
    try:
        value = json.loads(data)
    except (ValueError, RecursionError, UnicodeError):
        return
    if not isinstance(value, dict):
        return
    try:
        device = Device.from_json(value)
    except DeslocProtocolError:
        return
    assert len(device.mac) == 12 and all(c in "0123456789abcdef" for c in device.mac)  # nosec B101 - intentional test oracle
    assert device.battery is None or 0 <= device.battery <= 100  # nosec B101 - intentional test oracle
    assert device.rssi is None or -127 <= device.rssi <= 0  # nosec B101 - intentional test oracle
    assert device.is_locked in (None, True, False)  # nosec B101 - intentional test oracle


if __name__ == "__main__":
    atheris.Setup(sys.argv, atheris.instrument_func(test_one_input))
    atheris.Fuzz()
