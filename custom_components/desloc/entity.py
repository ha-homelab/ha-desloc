"""Shared device identity and availability."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DeslocCoordinator


class DeslocEntity(CoordinatorEntity[DeslocCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: DeslocCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_{key}"
        device = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.mac)}, manufacturer="DESLOC",
            name=device.name if device else "DESLOC C100 Plus",
            model=device.model if device else "C100 Plus",
            sw_version=device.firmware if device else None,
        )

    @property
    def available(self) -> bool:
        # Cloud reachability only; onlineStatus enum is not yet verified.
        return super().available and self.coordinator.data is not None
