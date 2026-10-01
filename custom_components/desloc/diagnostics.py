"""Allowlisted compatibility diagnostics without account or device identity."""
from typing import Any

from homeassistant.core import HomeAssistant

from . import DeslocConfigEntry
from .const import TESTED_MODELS


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DeslocConfigEntry,
) -> dict[str, Any]:
    """Exclude credentials, names, IDs, MACs, PINs, and raw vendor responses."""
    coordinator = getattr(entry, "runtime_data", None)
    device = coordinator.data if coordinator is not None else None
    return {
        "last_poll_success": bool(coordinator and coordinator.last_update_success),
        "device_present": device is not None,
        "device": None if device is None else {
            "model": device.model,
            "model_validation": "tested" if device.model in TESTED_MODELS else "experimental",
            "firmware": device.firmware,
            "battery_percent": device.battery,
            "wifi_rssi_dbm": device.rssi,
            "reported_bolt_code": device.door_state,
            "reported_online_code": device.online_status,
        },
    }
