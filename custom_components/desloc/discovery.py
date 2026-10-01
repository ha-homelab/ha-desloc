"""Reconcile an authenticated account into independent lock entries."""
import asyncio
from dataclasses import asdict, dataclass, field
import re

from homeassistant.config_entries import ConfigEntry, SOURCE_IGNORE, SOURCE_SYSTEM
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .api import Credentials, DeslocProtocolError, Device
from .const import CONF_CREDENTIALS, CONF_DEVICE_ID, CONF_MAC, DOMAIN

_STATE_KEY = f"{DOMAIN}_account_discovery"


@dataclass(frozen=True)
class ValidatedDevice:
    """An in-process handoff, never an HTTP payload or stored account digest."""

    device: Device = field(repr=False)
    credentials: Credentials = field(repr=False)
    auth_type: str

    def __post_init__(self) -> None:
        if (not isinstance(self.device, Device)
                or type(self.device.id) is not int or self.device.id <= 0
                or not isinstance(self.device.mac, str)
                or not re.fullmatch(r"[0-9a-f]{12}", self.device.mac)
                or not isinstance(self.credentials, Credentials)
                or self.auth_type not in ("account", "session")):
            raise ValueError("Invalid DESLOC device handoff")

    def entry_data(self) -> dict:
        return {CONF_MAC: self.device.mac, CONF_DEVICE_ID: self.device.id,
                CONF_CREDENTIALS: asdict(self.credentials), "auth_type": self.auth_type}


@dataclass
class _DiscoveryState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    active: ValidatedDevice | None = None


def _state(hass: HomeAssistant) -> _DiscoveryState:
    return hass.data.setdefault(_STATE_KEY, _DiscoveryState())


def is_valid_handoff(hass: HomeAssistant, value: object) -> bool:
    """Only the current authenticated reconciliation can create child entries."""
    state = _state(hass)
    return isinstance(value, ValidatedDevice) and state.lock.locked() and state.active is value


def _entry_mac(entry: ConfigEntry) -> str | None:
    # Ignored entries normally contain only their unique ID.
    return entry.data.get(CONF_MAC) or entry.unique_id


async def async_reconcile_devices(
    hass: HomeAssistant, devices: list[Device], credentials: Credentials,
    auth_type: str, *, target: ConfigEntry | None = None,
) -> int:
    """Add all returned locks and refresh matching sessions after interactive auth.

    This function is deliberately not called by polling or startup: an older
    session must never overwrite a session saved by a newer interactive login.
    The caller verifies its original target before entering this function.
    """
    # Validate the complete batch before making any configuration changes.
    handoffs: dict[str, ValidatedDevice] = {}
    for device in devices:
        handoff = ValidatedDevice(device, credentials, auth_type)
        previous = handoffs.get(device.mac)
        if previous is not None and previous.device.id != device.id:
            raise DeslocProtocolError("DESLOC returned conflicting identities for one lock")
        handoffs.setdefault(device.mac, handoff)
    if target is not None and _entry_mac(target) not in handoffs:
        raise DeslocProtocolError("Authenticated account does not contain the configured lock")
    state = _state(hass)
    created = 0
    reload_entries: list[ConfigEntry] = []
    async with state.lock:
        entries = hass.config_entries.async_entries(DOMAIN, include_ignore=True)
        by_mac = {_entry_mac(entry): entry for entry in entries}
        for mac, handoff in handoffs.items():
            if (entry := by_mac.get(mac)) is not None:
                if entry.source == SOURCE_IGNORE or entry is target:
                    continue
                changed = hass.config_entries.async_update_entry(
                    entry, data={**entry.data, **handoff.entry_data()})
                if changed and entry.disabled_by is None:
                    reload_entries.append(entry)
                continue
            state.active = handoff
            try:
                result = await hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_SYSTEM}, data=handoff)
            finally:
                state.active = None
            if result["type"] == FlowResultType.CREATE_ENTRY:
                created += 1
                by_mac[mac] = result["result"]
            elif result.get("reason") not in ("already_configured", "already_in_progress"):
                raise DeslocProtocolError("Could not add a DESLOC device to Home Assistant")
    for entry in reload_entries:
        # The initiating target is reloaded by its own flow only after it ends.
        # HA serializes reload against setup and clears stale peer reauth flows.
        hass.config_entries.async_schedule_reload(entry.entry_id)
    return created
